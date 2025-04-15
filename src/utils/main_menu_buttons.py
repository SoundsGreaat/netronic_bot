from telebot import types


def create_main_menu():
    main_menu = types.ReplyKeyboardMarkup(resize_keyboard=True)

    knowledge_base_button = types.KeyboardButton('🎓 Навчання')
    business_processes_button = types.KeyboardButton('💼 Бізнес-процеси')
    news_feed_button = types.KeyboardButton('🔗 Стрічка новин')
    contacts_button = types.KeyboardButton('📞 Контакти')
    make_card_button = types.KeyboardButton('📜 Меню подяк')
    birthday_button = types.KeyboardButton('🎂 Дні народження')
    support_button = types.KeyboardButton('💭 Зауваження по роботі боту')

    main_menu.row(knowledge_base_button, business_processes_button)
    main_menu.row(news_feed_button, contacts_button)
    main_menu.row(make_card_button, birthday_button)
    main_menu.row(support_button)

    return main_menu


main_menu = create_main_menu()
button_names = [btn['text'] for row in main_menu.keyboard for btn in row]
old_button_names = ['🎓 База знань', '🎅 Таємний Санта']
