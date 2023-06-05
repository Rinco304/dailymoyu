import io
import json
import base64
import httpx
import asyncio

from pathlib import Path
from typing import List
from hoshino import Service, aiorequests, priv
from hoshino.typing import MessageSegment
from nonebot.log import logger

data_path = Path("hoshino/modules/dailymoyu")
sub_data_path = data_path / "sub_group_data.json"

sv_help = '''
[订阅摸鱼日历] 启用后会在每天早上发送一份摸鱼日历
[取消订阅摸鱼日历] 取消订阅
[摸鱼日历] 手动发送一份日历
订阅功能后会在每天11点自动发送一份摸鱼日历
'''.strip()

sv = Service(
    name='摸鱼日历',
    enable_on_default=True,
    visible=True,
    bundle="娱乐",
    help_=sv_help
)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows; U; Windows NT 5.1; zh-CN; rv:1.9.1.6) ",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-cn"
}


async def get_calendar() -> str:
    async with httpx.AsyncClient(http2=True) as client:
        response = await client.get(
            url="https://api.j4u.ink/v1/store/other/proxy/remote/moyu.json",
            headers=headers
        )
    if response.is_error:
        raise ValueError(f"摸鱼日历获取失败，错误码：{response.status_code}")
    content = response.json()
    image_url = content["data"]["moyu_url"]
    try:
        image_bytes = await (await aiorequests.get(image_url, headers=headers)).content
        return f"base64://{base64.b64encode(io.BytesIO(image_bytes).getvalue()).decode()}"
    except Exception as e:
        sv.logger.critical(f"获取图片失败：{e}")
        return ""


@sv.scheduled_job('cron', hour='11', jitter=50)
async def automoyu():
    moyu_img = await get_calendar()
    if not moyu_img:
        sv.logger.warning("Error when getting moyu img")
        return
    sub_group_list = load_sub_list()
    for gid in sub_group_list['data_list']:
        message = MessageSegment.image(moyu_img)
        await sv.bot.send_group_msg(group_id=gid, message=message)
        await asyncio.sleep(5)


@sv.on_fullmatch('摸鱼日历')
async def handnews(bot, ev):
    moyu_img = await get_calendar()
    if not moyu_img:
        sv.logger.warning("Error when getting moyu img")
        return
    message = MessageSegment.image(moyu_img)
    await bot.send(ev, message)


@sv.on_fullmatch("订阅摸鱼日历")
async def sub_group(bot, ev):
    gid = ev.group_id
    u_priv = priv.get_user_priv(ev)
    if u_priv >= sv.manage_priv:
        try:
            sub_group_list = load_sub_list()
            if gid in sub_group_list['data_list']:
                await bot.send(ev, "本群已订阅此功能")
                return
            sub_group_list['data_list'].append(gid)
            dump_sub_list(sub_group_list)
            await bot.send(ev, "订阅成功~")
        except Exception as e:
            await bot.send(ev, f"出现错误:{e}")
    else:
        await bot.send(ev, "只有管理以上才能使用此指令哦~")


@sv.on_fullmatch("取消订阅摸鱼日历")
async def unsub_group(bot, ev):
    gid = ev.group_id
    u_priv = priv.get_user_priv(ev)
    if u_priv >= sv.manage_priv:
        try:
            sub_group_list = load_sub_list()
            if gid not in sub_group_list['data_list']:
                await bot.send(ev, "此群没有订阅此功能")
                return
            sub_group_list['data_list'].remove(gid)
            dump_sub_list(sub_group_list)
            await bot.send(ev, "取消订阅成功~")
        except Exception as e:
            await bot.send(ev, f"出现错误:{e}")
    else:
        await bot.send(ev, "只有管理以上才能使用此指令哦~")


def dump_sub_list(sub_group_list: List[int]):
    # sub_data_path.mkdir(parents=True, exist_ok=True)
    json.dump(
        sub_group_list,
        sub_data_path.open("w", encoding="utf-8"),
        indent=4,
        separators=(",", ": "),
        ensure_ascii=False,
    )

def load_sub_list() -> List[int]:
    if sub_data_path.exists():
        with sub_data_path.open("r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.decoder.JSONDecodeError:
                logger.warning("订阅列表解析错误，将重新获取")
                sub_data_path.unlink()
    return {"data_list":[]}
