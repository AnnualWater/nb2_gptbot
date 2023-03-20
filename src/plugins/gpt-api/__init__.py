# -*- coding: utf-8 -*-
# @Author:归年丶似水
# @Email:2448955276@qq.com
# @GitHub:github.com/AnnualWater
import datetime
import json
import os.path

import openai
from nonebot import get_bot
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, PrivateMessageEvent
from nonebot.plugin import on_startswith
from nonebot_plugin_apscheduler import scheduler

from .config import openai_api_key, openai_model_name, openai_proxy, session_max

# 配置OpenAI
if openai_api_key != "":
    openai.api_key = openai_api_key
if openai_proxy != "":
    openai.proxy = openai_proxy
if openai_model_name == "":
    openai_model_name = "gpt-3.5-turbo"

# session缓存
session: dict[int, list] = {}


# 定时清理
@scheduler.scheduled_job("cron", hour="*/8")
def auto_clear():
    global session
    session = {}
    return


# 响应函数
async def next_session(user_id, args) -> dict[str, str | bool]:
    if user_id not in session:
        session[user_id] = []
    session[user_id].append({"role": "user", "content": args})
    try:
        res_ = await openai.ChatCompletion.acreate(
            model=openai_model_name,
            messages=session[user_id]
        )
    except Exception as err:
        print(err)
        return {"success": False, "err": str(err)}
    res = res_.choices[0].message.content
    while res.startswith("\n") != res.startswith("？"):
        res = res[1:]
    session[user_id].append({"role": "assistant", "content": res})
    if len(session[user_id]) >= session_max:
        session[user_id] = []
        res = res + "\n历史对话达到上限，将自动清除历史记录"
    return {"success": True, "msg": res}


# 创建响应器chat
chat = on_startswith(msg="chat", ignorecase=True)


@chat.handle()
async def handle_gpt(event: MessageEvent):
    args = event.raw_message.replace("chat", "").replace(" ", "")
    if len(args) == 0:
        await chat.send(MessageSegment.text("聊天内容不能为空"), at_sender=True)
        return
    await chat.send(MessageSegment.text("ChatGPT正在思考中......"))
    response = await next_session(event.sender.user_id, args)
    if response["success"]:
        await chat.finish(MessageSegment.reply(event.message_id) + MessageSegment.text(response["msg"]))
    else:
        await chat.finish(MessageSegment.reply(event.message_id) + MessageSegment.text("错误！" + response["err"]))
    return


clear = on_startswith(msg="clear", ignorecase=True)


@clear.handle()
async def handle_clear(event: MessageEvent):
    session[event.user_id] = []
    await clear.send(MessageSegment.reply(event.message_id) + MessageSegment.text("清除成功！"))
    return


save = on_startswith(msg="save", ignorecase=True)


@save.handle()
async def handle_save(event: PrivateMessageEvent):
    if event.user_id not in session:
        await save.send(MessageSegment.reply(event.message_id) + MessageSegment.text("没有可保存的对话"))
        return
    file_name = f"{event.user_id}-{datetime.datetime.now().timestamp()}.json"
    with open(f"./{file_name}", "w", encoding='utf8') as f:
        json.dump(session[event.user_id], f, ensure_ascii=False)
        f.close()
    bot = get_bot()
    await bot.call_api(api="upload_private_file", user_id=event.user_id, file=os.path.abspath(f"./{file_name}"),
                       name=file_name)
