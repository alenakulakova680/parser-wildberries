"""
Telegram бот для парсинга товаров с Wildberries.
"""

import asyncio
import csv
import random
import glob
from datetime import datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

parsing_tasks = {}  # {user_id: asyncio.Task} - для управления задачами парсинга


def create_keyboards():
    """
    Создает клавиатуру с кнопками для взаимодействия с ботом.

    Returns:
        main (ReplyKeyboardMarkup or None): объект клавиатуры с кнопками или None при ошибке
    """
    try:
        main = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text='Что делает этот бот')],
            [KeyboardButton(text='Добавить категорию')],
            [KeyboardButton(text='Вывести изменение цен')],
            [KeyboardButton(text='Остановить парсинг')]
        ], input_field_placeholder='Выберите пункт меню..')
        return main
    except Exception as e:
        print(f"Ошибка создания клавиатуры: {e}")
        return None


def the_cheapest(data: list):
    """
    Находит товар с минимальной ценой.

    Args:
        data (List[List[Union[int, str]]]): Список списков с данными о товарах [артикул (int), цена (int), название (str), рейтинг (str)]

    Returns:
        cheapset (List[Union[int, str]] or None): Список с данными самого дешевого товара в формате 
                      [артикул (int), цена (int), название (str), рейтинг (str)] или None, если ошибка.
    """
    try:
        if not data or len(data) <= 1:
            return None
        products = data[:-1]
        cheapest = min(products, key=lambda x: x[1])
        return cheapest
    except Exception as e:
        print(f"Ошибка поиска минимальной цены: {e}")
        return None


async def main_parser(category: str):
    """
    Основная функция парсинга товаров с маркетплейса Wildberries.

    Args:
        category (str): Название категории товаров для поиска на Wildberries.

    Returns:
        list (List[List[Union[int, str]]]): Список списков с данными о товарах. Каждый внутренний список содержит:
              [артикул (int), цена (int), название (str), рейтинг (str)]

    Raises:
        Exception: При возникновении любых ошибок парсинга.
    """
    try:
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        ]
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option(
            "excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(f"--user-agent={random.choice(user_agents)}")
        driver = webdriver.Chrome(options=options, service=ChromeService(
            ChromeDriverManager().install()))

        try:
            main_url = 'https://www.wildberries.ru'
            driver.get(main_url)
            await asyncio.sleep(5)
            elem = driver.find_element(By.ID, "searchInput")
            elem.clear()
            staff_name = category
            await asyncio.sleep(1)
            elem.send_keys(staff_name)
            elem.send_keys(Keys.RETURN)
            await asyncio.sleep(5)
            urlpage = driver.current_url
            driver.get(urlpage)
            await asyncio.sleep(1)
            collected_data = []
            next_page_good = 1

            while next_page_good:
                i = 0
                await asyncio.sleep(0.3)
                cards_page_good = 1

                while cards_page_good:
                    await asyncio.sleep(0.1)
                    try:
                        element = driver.find_element(
                            By.CSS_SELECTOR, f'article[data-card-index="{i}"]')
                        driver.execute_script(
                            "arguments[0].scrollIntoView();", element)

                        for _ in range(14):
                            try:
                                content = driver.find_element(
                                    By.CSS_SELECTOR, f'article[data-card-index="{i}"]')
                                id = int(content.get_attribute("id")[1:])
                                price = int(content.find_element(
                                    By.CLASS_NAME, 'price__lower-price').text[:-2].replace(' ', ''))
                                name = content.find_element(
                                    By.CLASS_NAME, f'product-card__name').text

                                try:
                                    grade = content.find_element(
                                        By.CLASS_NAME, f'address-rate-mini').text
                                except Exception:
                                    grade = '0'

                                collected_data.append([])
                                collected_data[-1].append(id)
                                collected_data[-1].append(price)
                                collected_data[-1].append(name)
                                collected_data[-1].append(grade)
                                i += 1
                            except Exception:
                                cards_page_good = 0
                        await asyncio.sleep(0.2)
                    except Exception:
                        cards_page_good = 0

                try:
                    element_for_next = driver.find_element(
                        By.CLASS_NAME, "pagination-next")
                    element_for_next.send_keys(Keys.RETURN)
                except Exception:
                    next_page_good = 0

            driver.close()
            return collected_data
        except Exception as e:
            print(f"Ошибка при парсинге страницы: {e}")
            try:
                driver.close()
            except:
                pass
            raise
    except Exception as e:
        print(f"Общая ошибка в main_parser: {e}")
        raise


def sorted_data(collected_data: list):
    """
    Сортирует по артикулу и убирает дубликаты в списке.

    Args:
        collected_data (List[List[Union[int, str]]]): Список списков с данными о товарах. Каждый внутренний элемент содержит:
              [артикул (int), цена (int), название (str), рейтинг (str)]

    Returns:
        collected_data (List[List[Union[int, str]]]): Первоначальный список, отсортированный по возрастанию первого элемента(артикула).
              В списке отсутствуют дублирующие строчки.
              Каждый внутренний список содержит: [артикул (int), цена (int), название (str), рейтинг (str)]

    Raises:
        Exception: Ошибки при сортировке.
    """
    try:
        collected_data = sorted(collected_data, key=lambda x: x[0])
        i = 0
        while i < len(collected_data):
            j = i + 1
            while j < len(collected_data):
                if collected_data[i][0] == collected_data[j][0]:
                    collected_data.pop(j)
                else:
                    j += 1
            i += 1
        return collected_data
    except Exception as e:
        print(f"Ошибка в сортировке файла: {e}")
        raise

def save_to_csv(data: list, counter: int, user_id: int):
    """
    Сохраняет данные парсинга в CSV файл с добавлением временной метки.

    Args:
        data (List[List[Union[int, str]]]): Список списков с данными о товарах [артикул (int), цена (int), название (str), рейтинг(str)]
        counter (int): Порядковый номер файла.
        user_id (int): ID пользователя Telegram.

    Raises:
        Exception: При возникновении любых ошибок ввода-вывода или обработки данных.

    Returns:
        None: Функция не возвращает значения, только создает файл.
    """
    try:
        data.append([datetime.now().strftime('%d.%m.%Y %H:%M:%S')])
        filename = f'elements_{user_id}_{counter}.csv'
        with open(filename, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            for element_id in data:
                writer.writerow(element_id)
    except Exception as e:
        print(f"Ошибка сохранения в CSV для пользователя {user_id}: {e}")
        raise

async def parsing_analysis(counter: int, bot: Bot, chat_id: int):
    """
    Анализирует различия между двумя последовательными CSV файлами.
    Результаты анализа отправляются пользователю в Telegram чат.

    Args:
        counter (int): Номер текущей итерации парсинга.
        bot (Bot): Экземпляр бота Telegram для отправки сообщений.
        chat_id (int): Идентификатор чата Telegram (user_id).

    Returns:
        None: Функция не возвращает значения, только выводит пользователю информацию о изменениях.

    """
    try:
        user_id = chat_id

        try:
            with open(f'elements_{user_id}_{counter-1}.csv', 'r', encoding='utf-8') as f1:
                reader1 = csv.reader(f1)
                rows1 = list(reader1)
        except FileNotFoundError:
            await bot.send_message(chat_id=chat_id, text="Предыдущий файл данных не найден.")
            return

        try:
            with open(f'elements_{user_id}_{counter}.csv', 'r', encoding='utf-8') as f2:
                reader2 = csv.reader(f2)
                rows2 = list(reader2)
        except FileNotFoundError:
            await bot.send_message(chat_id=chat_id, text="Текущий файл данных не найден.")
            return

        differences = False
        message_parts = []

        if len(rows1) != len(rows2):
            differences = True
            if len(rows1) > len(rows2):
                message_parts.append(
                    f"Количество товаров уменьшилось на {len(rows1)-len(rows2)}")
            else:
                message_parts.append(
                    f"Ура! появилось {len(rows2)-len(rows1)} новых товаров")
        else:
            message_parts.append("Количество товаров не изменилось")

        i = j = 0
        new_items = []
        removed_items = []
        price_changes = []
        while i < len(rows1)-1 and j < len(rows2)-1:
            try:
                if rows1[i] != rows2[j]:
                    differences = True
                    if rows1[i][0] != rows2[j][0]:
                        if j+1 < len(rows2) and rows1[i][0] == rows2[j+1][0]:
                            new_items.append(
                                f'Артикул: {rows2[j][0]}, Имя: {rows2[j][2]}, Цена: {rows2[j][1]}')
                            j += 1
                        elif i+1 < len(rows1) and rows1[i+1][0] == rows2[j][0]:
                            removed_items.append(
                                f'Артикул: {rows1[i][0]}, Имя: {rows1[i][2]}, Цена: {rows1[i][1]}')
                            i += 1
                    elif rows1[i][1] != rows2[j][1]:
                        price_changes.append(
                            f'Цена товара {rows2[j][0]} изменилась на {int(rows2[j][1]) - int(rows1[i][1])} руб.')
            except Exception as e:
                print(f"Ошибка при сравнении строк: {e}")
            i += 1
            j += 1

        if differences:
            if new_items:
                message_parts.append("\n*Новые товары:*")
                message_parts.extend(new_items[:10])

            if removed_items:
                message_parts.append("\n*Удаленные товары:*")
                message_parts.extend(removed_items[:10])

            if price_changes:
                message_parts.append("\n*Изменения цен:*")
                message_parts.extend(price_changes[:10])
        else:
            message_parts.append("\n*Изменений не обнаружено*")

        if bot and chat_id:
            message_text = "\n".join(message_parts)
            if len(message_text) > 4096:
                message_text = message_text[:4090] + "..."
            await bot.send_message(
                chat_id=chat_id,
                text=message_text,
            )
    except Exception as e:
        print(f"Ошибка в parsing_analysis: {e}")
        if bot and chat_id:
            await bot.send_message(chat_id=chat_id, text=f"Ошибка при анализе данных: {str(e)}")


async def show_article_price(article: str, user_id: int):
    """
    Извлекает историю цен для указанного артикула из CSV файлов парсинга.

    Args:
        article (str): Артикул товара для поиска в истории.
        user_id (int): ID пользователя Telegram.

    Returns:
        message_text (str): Отформатированный текст с историей цен.
    """
    try:
        message_text = f"История цены артикула {article}:\n\n"
        found_any = False

        user_files = glob.glob(f'elements_{user_id}_*.csv')

        if not user_files:
            return f"Для вашей категории еще нет истории парсинга."

        def get_file_number(file_path):
            try:
                return int(file_path.split('_')[2].split('.')[0])
            except:
                return -1

        user_files.sort(key=get_file_number)

        for file_path in user_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1].strip()
                        for line in lines[:-1]:
                            parts = line.strip().split(',')
                            if parts[0] == article:
                                try:
                                    price = int(parts[1])
                                    message_text += f"Время: {last_line}\nЦена: {price} руб.\n\n"
                                    found_any = True
                                except (ValueError, IndexError):
                                    continue
                                break
            except Exception as e:
                print(f"Ошибка чтения файла {file_path}: {e}")
                continue

        if not found_any:
            message_text = f"Артикул {article} не найден в истории вашей категории."

        return message_text
    except Exception as e:
        print(f"Ошибка в show_article_price для пользователя {user_id}: {e}")
        return


async def start_parsing_task(user_id: int, category: str, interval_minutes: int, bot: Bot):
    """
    Запускает фоновую задачу парсинга для конкретного пользователя.

    Args:
        user_id (int): ID пользователя Telegram.
        category (str): Категория товаров для парсинга.
        interval_minutes (int): Интервал между парсингами в минутах.
        bot (Bot): Экземпляр бота Telegram.

    Returns:
        None: Функция не возвращает значения, только запускает задачу парсинга.

    """
    counter = 0

    while True:
        try:
            try:
                await bot.send_message(user_id, f'Начинаем парсинг категории "{category}"...')
            except Exception as e:
                print(
                    f"Ошибка отправки сообщения о начале парсинга для пользователя {user_id}: {e}")

            try:
                parsing_data = await main_parser(category)
            except Exception as e:
                await bot.send_message(user_id, f"Ошибка при выполнении парсинга: {str(e)}")
                await asyncio.sleep(60)
                continue

            try:
                parsing_data = sorted_data(parsing_data)
            except Exception as e:
                await bot.send_message(user_id, f"Ошибка при сортировке данных: {str(e)}")
                await asyncio.sleep(60)
                continue

            try:
                save_to_csv(parsing_data, counter, user_id)
            except Exception as e:
                await bot.send_message(user_id, f"Ошибка сохранения данных: {str(e)}")
                await asyncio.sleep(60)
                continue

            try:
                cheapest = the_cheapest(parsing_data)
                if cheapest:
                    await bot.send_message(
                        user_id,
                        f'Самый дешёвый товар:\n'
                        f'Артикул: {cheapest[0]}\n'
                        f'Цена: {cheapest[1]} руб.\n'
                        f'Имя: {cheapest[2]}'
                    )
            except Exception as e:
                print(
                    f"Ошибка отправки информации о самом дешевом товаре для пользователя {user_id}: {e}")

            if counter > 0:
                try:
                    await parsing_analysis(counter, bot, user_id)
                except Exception as e:
                    print(
                        f"Ошибка анализа данных для пользователя {user_id}: {e}")
                    await bot.send_message(user_id, f"Ошибка анализа изменений: {str(e)}")

            counter += 1

            try:
                await bot.send_message(
                    user_id,
                    f'Парсинг категории "{category}" завершен. '
                    f'Следующий через {interval_minutes} минут.'
                )
            except Exception as e:
                print(
                    f"Ошибка отправки сообщения о завершении для пользователя {user_id}: {e}")

            try:
                await asyncio.sleep(60*interval_minutes)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(
                    f"Ошибка во время ожидания для пользователя {user_id}: {e}")
                await asyncio.sleep(60)

        except asyncio.CancelledError:
            try:
                await bot.send_message(user_id, "Парсинг был остановлен.")
            except:
                pass
            break
        except Exception as e:
            print(
                f"Критическая ошибка в задаче парсинга для пользователя {user_id}: {e}")
            try:
                await bot.send_message(user_id, f"Критическая ошибка при парсинге: {str(e)}")
            except:
                pass
            await asyncio.sleep(60)


router = Router()
"""Основной роутер для обработки сообщений и команд бота."""

kb = create_keyboards()
"""Создание клавиатуры."""

class Register(StatesGroup):
    """
    Класс состояний для машины состояний (FSM) бота.

    Attributes:
        name (State): Состояние ввода названия категории товаров.
        time (State): Состояние ввода интервала парсинга в минутах.
        article (State): Состояние ввода артикула товара для отслеживания истории цен.
    """
    name = State()
    time = State()
    article = State()

@router.message(CommandStart())
async def cmd_start(message: Message):
    """
    Обработчик команды /start для Telegram-бота парсинга Wildberries.
    Отправляет приветственное сообщение и главное меню с доступными действиями.

    Args:
        message (Message): Объект входящего сообщения от пользователя Telegram.
            Содержит информацию о пользователе, чате и метаданные.

    """
    try:
        await message.answer("Привет! Я бот для парсинга товаров с Wildberries.", reply_markup=kb)
        await message.answer("Выберите действие в меню:")
    except Exception as e:
        print(f"Ошибка в команде /start: {e}")


@router.message(F.text == 'Что делает этот бот')
async def category(message: Message):
    """
    Обработчик входящего текста 'Что делает этот бот'.
    Функция представляет пользователю краткую информацию о функционале бота.

    Args:
        message (Message): Объект входящего сообщения от пользователя Telegram.
            Содержит информацию о пользователе, чате и метаданные.

    """
    try:
        await message.answer("Этот бот парсит товары категории, предупреждает о изменении цены и отслеживает всё")
    except Exception as e:
        print(f"Ошибка при показе описания бота: {e}")


@router.message(F.text == 'Добавить категорию')
async def register(message: Message, state: FSMContext):
    """
    Инициирует многошаговый диалог с пользователем, устанавливая первое
    состояние FSM (Register.name) и запрашивая название категории товара.

    Args:
        message (Message): Объект входящего сообщения от пользователя.
        state (FSMContext): Контекст машины состояний (FSM) для управления диалогом.

    """
    try:
        await state.set_state(Register.name)
        await message.answer("Введите категорию товара:")
    except Exception as e:
        print(f"Ошибка при начале регистрации категории: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")


@router.message(Register.name)
async def register_name(message: Message, state: FSMContext):
    """
    Сохраняет введенное пользователем название категории в состоянии FSM
    и переводит диалог в следующее состояние (Register.time).

    Args:
        message (Message): Объект входящего сообщения с названием категории.
        state(FSMContext): Контекст машины состояний для сохранения данных.
    """
    try:
        await state.update_data(name=message.text)
        await state.set_state(Register.time)
        await message.answer("Введите периодичность парсинга (в минутах):")
    except Exception as e:
        print(f"Ошибка при сохранении категории: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")


@router.message(Register.time)
async def parsing(message: Message, state: FSMContext):
    """
    Завершает регистрацию категории и запускает задачу парсинга.

    Обрабатывает введенный интервал, останавливает предыдущие задачи пользователя
    (если есть), сохраняет конфигурацию и запускает асинхронную задачу парсинга.

    Args:
        message (Message): Объект входящего сообщения с интервалом парсинга.
        state (FSMContext): Контекст машины состояний для сохранения данных.

    Returns:
        None

    Raises:
        ValueError: Если интервал не является положительным числом.

    """
    user_id = message.from_user.id

    try:
        try:
            interval = int(message.text)
            if interval <= 0:
                await message.answer("Периодичность должна быть положительным числом. Попробуйте снова.")
                return
        except ValueError:
            await message.answer("Пожалуйста, введите число (минуты). Попробуйте снова.")
            return

        await state.update_data(time=message.text)
        data = await state.get_data()

        parsing_task = asyncio.create_task(
            start_parsing_task(user_id, data['name'], interval, message.bot)
        )
        parsing_tasks[user_id] = parsing_task

        await message.answer(
            f'Вы подписались на категорию "{data["name"]}"\n'
            f'Обновления товаров будут проверяться каждые {data["time"]} минут.\n'
            f'Для остановки нажмите "Остановить парсинг"\n\n'
        )
        await state.clear()
    except Exception as e:
        print(f"Ошибка при запуске парсинга для пользователя {user_id}: {e}")
        await message.answer(f"Произошла ошибка при запуске парсинга: {str(e)}")
        await state.clear()


@router.message(F.text == 'Остановить парсинг')
async def stop_parsing(message: Message):
    """
    Останавливает активную задачу парсинга для текущего пользователя.

    Args:
        message (Message): Объект входящего сообщения от пользователя 'Остановить парсинг'.
    """
    user_id = message.from_user.id

    try:
        if user_id in parsing_tasks:
            task = parsing_tasks[user_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            del parsing_tasks[user_id]
            await message.answer("Парсинг успешно остановлен!")
        else:
            await message.answer("У вас нет активных задач парсинга.")
    except Exception as e:
        print(f"Ошибка при остановке парсинга для пользователя {user_id}: {e}")
        await message.answer(f"Ошибка при остановке парсинга: {str(e)}")


@router.message(F.text == 'Вывести изменение цен')
async def show_price_changes(message: Message, state: FSMContext):
    """
    Инициирует процесс получения истории изменения цен для конкретного артикула.

    Args:
        message (Message): Входящее сообщение от пользователя с текстом 'Вывести изменение цен'.
        state (FSMContext): Контекст конечного автомата состояний.

    """
    try:
        await message.answer("Введите артикул товара вашей категории который вас интересует:")
        await state.set_state(Register.article)
    except Exception as e:
        print(f"Ошибка при запросе артикула: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")


@router.message(Register.article)
async def article(message: Message, state: FSMContext):
    """
    Выводит полльзователю историю изменения цены товара по артикулу.

    Args:
        message (Message): Входящее сообщение от пользователя с текстом 'Вывести изменение цен'.
        state (FSMContext): Контекст конечного автомата состояний.

    """
    try:
        user_id = message.from_user.id
        await state.update_data(article=message.text)
        data = await state.get_data()

        await message.answer(f'Ищу историю цены товара с артикулом {data["article"]}...')

        article_history = await show_article_price(data["article"], user_id)

        await message.answer(article_history)
        await state.clear()
    except Exception as e:
        print(
            f"Ошибка при показе истории цены для пользователя {user_id}: {e}")
        await message.answer(f"Произошла ошибка при поиске истории цены: {str(e)}")
        await state.clear()


async def main():
    """
    Основная функция запуска Telegram бота.

    Инициализирует компоненты бота, очищает глобальные состояния и запускает
    обработку входящих сообщений.
    """
    try:
        bot = Bot(token="8534686350:AAHSYTJLfjmakcMWBhoFSu8oR0RZiB2_EFU")
        dp = Dispatcher()
        dp.include_router(router)
        parsing_tasks.clear()  
        await dp.start_polling(bot)
    except Exception as e:
        print(f"Критическая ошибка в основном цикле бота: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
