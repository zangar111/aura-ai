from handlers import account, assistant, charts, common, schedule

# Порядок важен: ИИ получает только то, что не забрали команды.
routers = [
    common.router,
    charts.router,
    schedule.router,
    account.router,
    assistant.router,
]
