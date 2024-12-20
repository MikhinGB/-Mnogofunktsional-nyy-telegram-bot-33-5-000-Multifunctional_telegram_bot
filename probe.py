import telebot
from PIL import Image, ImageOps
import io
from telebot import types
import os


TOKEN = os.environ['TOKEN']
bot = telebot.TeleBot(TOKEN)

user_states = {}  # тут будем хранить информацию о действиях пользователя

ASCII_CHARS = ''
type_mirror = ''


def resize_image(image, new_width=100):

    """ Изменяет размер изображения с сохранением пропорций."""

    width, height = image.size
    ratio = height / width
    new_height = int(new_width * ratio)
    return image.resize((new_width, new_height))

def invert_colors(image):

    """ Преобразует изображение в инверсионное (эффект негатива) """

    im_invert = ImageOps.invert(image)
    return im_invert

def mirror_image(image):

    """ Преобразует изображение в зеркальное """
    if type_mirror == 'Y':
        im_flipped = image.transpose(method=Image.Transpose.FLIP_LEFT_RIGHT)
    else:
        im_flipped = image.transpose(method=Image.Transpose.FLIP_TOP_BOTTOM)
    return im_flipped


def grayify(image):

    """ Преобразует цветное изображение в оттенки серого. """

    return image.convert("L")


def image_to_ascii(image_stream, new_width=40):

    """ Основная функция для преобразования изображения в ASCII-арт. Изменяет размер, преобразует в градации серого
    и затем в строку ASCII-символов."""

    # Переводим в оттенки серого
    image = Image.open(image_stream).convert('L')

    # меняем размер сохраняя отношение сторон
    width, height = image.size
    aspect_ratio = height / float(width)
    new_height = int(
        aspect_ratio * new_width * 0.55)  # 0,55 так как буквы выше чем шире
    img_resized = image.resize((new_width, new_height))

    img_str = pixels_to_ascii(img_resized)
    img_width = img_resized.width

    max_characters = 4000 - (new_width + 1)
    max_rows = max_characters // (new_width + 1)

    ascii_art = ""
    for i in range(0, min(max_rows * img_width, len(img_str)), img_width):
        ascii_art += img_str[i:i + img_width] + "\n"

    return ascii_art


def pixels_to_ascii(image):

    """ Конвертирует пиксели изображения в градациях серого в строку ASCII-символов, используя предопределенную строку
    ASCII_CHARS"""

    pixels = image.getdata()
    characters = ""
    for pixel in pixels:
        characters += ASCII_CHARS[pixel * len(ASCII_CHARS) // 256]
    return characters


# Огрубляем изображение
def pixelate_image(image, pixel_size):

    """ Принимает изображение и размер пикселя. Уменьшает изображение до размера, где один пиксель представляет большую
     область, затем увеличивает обратно, создавая пиксельный эффект."""

    image = image.resize(
        (image.size[0] // pixel_size, image.size[1] // pixel_size),
        Image.Resampling.NEAREST
    )
    image = image.resize(
        (image.size[0] * pixel_size, image.size[1] * pixel_size),
        Image.Resampling.NEAREST
    )
    return image


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):

    """ Обработчик сообщений, реагирует на команды /start и /help, отправляя приветственное сообщение. """

    bot.reply_to(message, "Send me an image, and I'll provide options for you!")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):

    """ Обработчик сообщений, реагирует на изображения, отправляемые пользователем. Предлагает
    пользователю ввести уникальный набор символов ASCII и выбрать варианты обработки."""

    bot.reply_to(message, "I got your photo! Please choose what you'd like to do with it.",
                 reply_markup=get_options_keyboard())
    user_states[message.chat.id] = {'photo': message.photo[-1].file_id}
    # bot.reply_to(message, "Введите набор символов ASCII без пробелов, без запятых....")
    # bot.register_next_step_handler(message, save_ascii_chars)

@bot.message_handler(content_types=['text'])
def save_ascii_chars(message):

    """ Обработчик сообщений, принимает уникальный набор символов ASCII, введенный пользователем."""

    global ASCII_CHARS
    ASCII_CHARS = message.text
    bot.reply_to(message, f'Ваши данные успешно сохранены!')


def get_options_keyboard():

    """ Создает клавиатуру с кнопками для выбора пользователем, как обработать изображение: через пикселизацию или
    преобразование в ASCII-арт, сделать негативное изображение или зеркальное отображение """

    keyboard = types.InlineKeyboardMarkup()
    pixelate_btn = types.InlineKeyboardButton("Pixelate", callback_data="pixelate")
    ascii_btn = types.InlineKeyboardButton("ASCII Art", callback_data="ascii")
    negative_btn = types.InlineKeyboardButton("Negative", callback_data="negative")
    mirror_btn = types.InlineKeyboardButton("Mirror", callback_data="mirror")
    keyboard.add(pixelate_btn, ascii_btn, negative_btn, mirror_btn)
    return keyboard


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):

    """ Определяет действия в ответ на выбор пользователя (например, пикселизация или ASCII-арт) и вызывает
    соответствующую функцию обработки.
"""
    if call.data == "pixelate":
        bot.answer_callback_query(call.id, "Pixelating your image...")
        pixelate_and_send(call.message)
    elif call.data == "ascii":
        bot.answer_callback_query(call.id, "Converting your image to ASCII art...")
        ascii_and_send(call.message)
    elif call.data == "negative":
        bot.answer_callback_query(call.id, "Creating a negative your image...")
        invert_and_send(call.message)
    elif call.data == "mirror":
        handle_mirror("mirror")
        bot.answer_callback_query(call.id, "Creating a mirror your image...")
        mirror_and_send(call.message)

@bot.message_handler(content_types=None)
def handle_mirror(message):
    bot.reply_to(message, "Зеркалим горизонтально? (Y/N):  ")
    bot.register_next_step_handler(message, save_type_mirror)

@bot.message_handler(content_types=['text'])
def save_type_mirror(message):

    """ Обработчик сообщений, принимает ответ от пользователя на вопрос о виде отражения ."""

    global type_mirror
    type_mirror = message.text

def pixelate_and_send(message):

    """ Пикселизирует изображение и отправляет его обратно пользователю."""

    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)
    pixelated = pixelate_image(image, 20)

    output_stream = io.BytesIO()
    pixelated.save(output_stream, format="JPEG")
    output_stream.seek(0)
    bot.send_photo(message.chat.id, output_stream)


def ascii_and_send(message):

    """ Преобразует изображение в ASCII-арт и отправляет результат в виде текстового сообщения."""
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    ascii_art = image_to_ascii(image_stream)
    bot.send_message(message.chat.id, f"```\n{ascii_art}\n```", parse_mode="MarkdownV2")


def invert_and_send(message):

    """ Преобразует изображение в 'негатив' и  отправляет его обратно пользователю. """
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)
    inverted = invert_colors(image)

    output_stream = io.BytesIO()
    inverted.save(output_stream, format="JPEG")
    output_stream.seek(0)
    bot.send_photo(message.chat.id, output_stream)


def mirror_and_send(message):

    """ Преобразует изображение в зеркальное и отправляет его обратно пользователю. """
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)
    reflected_mirror = mirror_image(image)

    output_stream = io.BytesIO()
    reflected_mirror.save(output_stream, format="JPEG")
    output_stream.seek(0)
    bot.send_photo(message.chat.id, output_stream)


bot.polling(none_stop=True)
