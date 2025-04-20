import json
from datetime import datetime
from typing import List, Dict, Any, Optional, AsyncGenerator

from astrbot.api.event import AstrMessageEvent
import astrbot.api.message_components as Comp
from astrbot.api import logger

from .dao import SteamDAO
from .steam_api_client import SteamAPIClient


class SteamCommandHandlers:
    """Steam 命令处理器类，封装所有命令的业务逻辑"""
    
    def __init__(self, dao: SteamDAO, client: SteamAPIClient, send_to_user, send_to_group):
        """初始化命令处理器
        
        Args:
            dao: 数据访问对象
            client: Steam API客户端
            send_to_user: 发送私聊消息的函数
            send_to_group: 发送群聊消息的函数
        """
        self.dao = dao
        self.client = client
        self.send_to_user = send_to_user
        self.send_to_group = send_to_group
    
    async def handle_bind(self, event: AstrMessageEvent) -> AsyncGenerator:
        """处理 /steam_bind 命令"""
        args = event.message_str.split()
        if len(args) < 2:
            yield event.plain_result("❌ 请提供 Steam ID，格式: /steam_bind <steamid>")
            return
            
        steamid = args[1]
        qq_id = event.get_sender_id()
        
        self.dao.bind_steam_id(qq_id, steamid)
        yield event.plain_result(f"✅ 已绑定 SteamID：{steamid}")
    
    async def handle_notify_group(self, event: AstrMessageEvent) -> AsyncGenerator:
        """处理 /steam_notify_group 命令"""
        args = event.message_str.split()
        if len(args) < 2:
            yield event.plain_result("❌ 参数不足, 格式: /steam_notify_group <add/remove/list> [群号] [参数]")
            return
            
        action = args[1]
        qq_id = event.get_sender_id()
        
        if action == "list":
            prefs_rows = self.dao.get_notify_prefs(qq_id)
            text = "\n".join(f"{r[0]} → {r[1]}" for r in prefs_rows) or "无订阅"
            yield event.plain_result(f"已订阅设置：\n{text}")
            return
            
        if len(args) < 3:
            yield event.plain_result("❌ 请提供群号")
            return
            
        group_id = args[2]
        
        if action == "add":
            # 解析参数
            prefs = {}
            for param in args[3:]:
                if "=" in param:
                    key, value = param.split("=", 1)
                    if key == "only_game":
                        prefs[key] = value.lower() == "true"
                    elif key == "mute":
                        prefs[key] = [value]
                    elif key == "friends":
                        prefs[key] = value.split(",")
            
            self.dao.set_notify_prefs(qq_id, group_id, prefs)
            yield event.plain_result(f"✅ 群 {group_id} 通知已添加，偏好：{json.dumps(prefs)}")
            
        elif action == "remove":
            self.dao.remove_notify_prefs(qq_id, group_id)
            yield event.plain_result(f"✅ 群 {group_id} 通知已移除")
        else:
            yield event.plain_result("❌ 未知操作，支持的操作：add/remove/list")
    
    async def handle_achievements(self, event: AstrMessageEvent) -> AsyncGenerator:
        """处理 /steam_achievements 命令"""
        args = event.message_str.split()
        if len(args) < 2:
            yield event.plain_result("❌ 请提供游戏 AppID，格式: /steam_achievements <appid>")
            return
            
        try:
            appid = int(args[1])
        except ValueError:
            yield event.plain_result("❌ AppID 必须是数字")
            return
            
        qq_id = event.get_sender_id()
        steamid = self.dao.get_steam_id(qq_id)
        if not steamid:
            yield event.plain_result("❌ 您尚未绑定 Steam ID。请先使用 /steam_bind <steamid> 命令绑定")
            return
        
        # 获取游戏成就信息
        achievement_data = await self.client.get_achievements(steamid, appid)
        game_schema = await self.client.get_all_achievements(appid)
        
        if not achievement_data.get("playerstats", {}).get("achievements"):
            yield event.plain_result("❌ 获取成就信息失败，可能是游戏不支持成就系统或您没有这款游戏")
            return
            
        playerstats = achievement_data["playerstats"]
        game_name = playerstats.get("gameName", f"AppID: {appid}")
        achievements = playerstats.get("achievements", [])
        
        # 统计成就完成情况
        total = len(achievements)
        completed = sum(1 for a in achievements if a.get("achieved", 0) == 1)
        completion_rate = completed / total * 100 if total > 0 else 0
        
        # 查找未完成的成就
        uncompleted = [a for a in achievements if a.get("achieved", 0) == 0]
        
        # 构建结果消息
        result = [
            Comp.Plain(f"🎮 {game_name} 成就完成情况\n"),
            Comp.Plain(f"完成进度: {completed}/{total} ({completion_rate:.1f}%)\n\n")
        ]
        
        if uncompleted:
            result.append(Comp.Plain("📌 未完成的成就（前5个）:\n"))
            for i, ach in enumerate(uncompleted[:5]):
                schema_data = next((a for a in game_schema.get("game", {}).get("availableGameStats", {}).get("achievements", []) 
                                   if a.get("name") == ach.get("apiname")), {})
                ach_name = schema_data.get("displayName", ach.get("apiname", "未知成就"))
                ach_desc = schema_data.get("description", "")
                result.append(Comp.Plain(f"{i+1}. {ach_name}: {ach_desc}\n"))
        
        yield event.chain_result(result)
    
    async def handle_games(self, event: AstrMessageEvent) -> AsyncGenerator:
        """处理 /steam_games 命令"""
        args = event.message_str.split()
        show_top = False
        if len(args) > 1 and args[1].lower() == "top":
            show_top = True
            
        qq_id = event.get_sender_id()
        steamid = self.dao.get_steam_id(qq_id)
        if not steamid:
            yield event.plain_result("❌ 您尚未绑定 Steam ID。请先使用 /steam_bind <steamid> 命令绑定")
            return
        
        # 获取游戏库信息
        games_data = await self.client.get_owned_games(steamid)
        games = games_data.get("response", {}).get("games", [])
        
        if not games:
            yield event.plain_result("❌ 无法获取游戏库信息，可能是账号私密或没有游戏")
            return
            
        # 统计游戏库信息
        total_games = len(games)
        total_playtime = sum(g.get("playtime_forever", 0) for g in games) / 60  # 转换为小时
        
        # 排序游戏，按游戏时间降序
        sorted_games = sorted(games, key=lambda g: g.get("playtime_forever", 0), reverse=True)
        
        # 构建结果消息
        result = [
            Comp.Plain(f"🎮 Steam 游戏库统计\n"),
            Comp.Plain(f"游戏总数: {total_games} 款\n"),
            Comp.Plain(f"总游戏时间: {total_playtime:.1f} 小时\n\n")
        ]
        
        if show_top:
            result.append(Comp.Plain("⏱️ 游戏时间排行（前10）:\n"))
            for i, game in enumerate(sorted_games[:10]):
                name = game.get("name", f"AppID: {game.get('appid')}")
                hours = game.get("playtime_forever", 0) / 60
                result.append(Comp.Plain(f"{i+1}. {name}: {hours:.1f}小时\n"))
        
        yield event.chain_result(result)

    async def handle_subscribe(self, event: AstrMessageEvent) -> AsyncGenerator:
        """处理 /steam_subscribe 命令"""
        args = event.message_str.split()
        if len(args) < 2:
            yield event.plain_result("❌ 参数不足，格式: /steam_subscribe <add/remove/list> [appid] [选项]")
            return
            
        action = args[1]
        qq_id = event.get_sender_id()
        
        if action == "list":
            rows = self.dao.get_game_subscriptions(qq_id)
            if not rows:
                yield event.plain_result("您没有订阅任何游戏")
                return
                
            result = ["您当前订阅的游戏：\n"]
            for appid, news, deals in rows:
                game_details = await self.client.get_game_details(appid)
                game_name = game_details.get(str(appid), {}).get("data", {}).get("name", f"AppID: {appid}")
                subs = []
                if news:
                    subs.append("新闻")
                if deals:
                    subs.append("特惠")
                result.append(f"- {game_name} ({appid}): {'+'.join(subs)}\n")
                
            yield event.plain_result("".join(result))
            return
            
        if len(args) < 3:
            yield event.plain_result("❌ 请提供游戏 AppID")
            return
            
        try:
            appid = int(args[2])
        except ValueError:
            yield event.plain_result("❌ AppID 必须是数字")
            return
            
        if action == "add":
            # 解析选项
            news = True
            deals = True
            for param in args[3:]:
                if "=" in param:
                    key, value = param.split("=", 1)
                    if key == "news":
                        news = value.lower() == "true"
                    elif key == "deals":
                        deals = value.lower() == "true"
            
            # 验证游戏是否存在
            game_details = await self.client.get_game_details(appid)
            if not game_details.get(str(appid), {}).get("data"):
                yield event.plain_result("❌ 未找到该游戏，请确认 AppID 是否正确")
                return
                
            game_name = game_details[str(appid)]["data"]["name"]
            
            self.dao.subscribe_game(qq_id, appid, news, deals)
            
            options = []
            if news:
                options.append("新闻")
            if deals:
                options.append("特惠")
                
            yield event.plain_result(f"✅ 已订阅 {game_name} 的{'+'.join(options)}信息")
            
        elif action == "remove":
            self.dao.unsubscribe_game(qq_id, appid)
            yield event.plain_result(f"✅ 已取消订阅 AppID: {appid} 的所有信息")
            
        else:
            yield event.plain_result("❌ 未知操作，支持的操作：add/remove/list")
    
    async def handle_market(self, event: AstrMessageEvent) -> AsyncGenerator:
        """处理 /steam_market 命令"""
        args = event.message_str.split()
        if len(args) < 2:
            yield event.plain_result("❌ 参数不足，格式: /steam_market <watch/unwatch/list> [appid] [物品名] [期望价格]")
            return
            
        action = args[1]
        qq_id = event.get_sender_id()
        
        if action == "list":
            rows = self.dao.get_market_watches(qq_id)
            if not rows:
                yield event.plain_result("您没有监控任何市场物品")
                return
                
            result = ["您当前监控的物品：\n"]
            for id, appid, hash_name, desired, last in rows:
                result.append(f"ID: {id} - {hash_name} (AppID: {appid})\n")
                result.append(f"  期望价格: ¥{desired:.2f} | 当前价格: ¥{last:.2f if last else 0.00}\n")
                
            yield event.plain_result("".join(result))
            return
            
        if action == "unwatch":
            if len(args) < 3:
                yield event.plain_result("❌ 请提供要取消的监控 ID")
                return
                
            try:
                watch_id = int(args[2])
            except ValueError:
                yield event.plain_result("❌ ID 必须是数字")
                return
                
            self.dao.remove_market_watch(watch_id, qq_id)
            yield event.plain_result(f"✅ 已取消 ID 为 {watch_id} 的物品价格监控")
            return
            
        if action == "watch":
            if len(args) < 5:
                yield event.plain_result("❌ 参数不足，格式: /steam_market watch <appid> <物品市场哈希名> <期望价格>")
                return
                
            try:
                appid = int(args[2])
                market_hash_name = args[3]
                desired_price = float(args[4])
            except (ValueError, IndexError):
                yield event.plain_result("❌ 参数格式错误，请确保 AppID 和期望价格是有效数字")
                return
                
            # 获取当前价格
            price_data = await self.client.get_market_price(appid, market_hash_name)
            if not price_data.get("success"):
                yield event.plain_result("❌ 无法获取该物品的价格信息，请确认物品名称是否正确")
                return
                
            lowest_price = price_data.get("lowest_price", "")
            if lowest_price:
                # 移除货币符号并转换为浮点数
                try:
                    current_price = float(lowest_price.replace("¥", "").strip())
                except ValueError:
                    current_price = None
            else:
                current_price = None
                
            watch_id = self.dao.add_market_watch(qq_id, appid, market_hash_name, desired_price, current_price)
            
            yield event.plain_result(
                f"✅ 已添加物品 {market_hash_name} 的价格监控\n"
                f"当前价格: {lowest_price or '未知'}\n"
                f"目标价格: ¥{desired_price:.2f}\n"
                f"监控 ID: {watch_id}"
            )
        else:
            yield event.plain_result("❌ 未知操作，支持的操作：watch/unwatch/list")
    
    async def handle_news(self, event: AstrMessageEvent) -> AsyncGenerator:
        """处理 /steam_news 命令"""
        args = event.message_str.split()
        if len(args) < 2:
            yield event.plain_result("❌ 请提供游戏 AppID，格式: /steam_news <appid> [count=3]")
            return
            
        try:
            appid = int(args[1])
        except ValueError:
            yield event.plain_result("❌ AppID 必须是数字")
            return
            
        count = 3
        if len(args) > 2 and "=" in args[2]:
            key, value = args[2].split("=", 1)
            if key == "count":
                try:
                    count = int(value)
                    count = min(max(count, 1), 5)  # 限制在1-5条之间
                except ValueError:
                    pass
        
        # 获取游戏信息和新闻
        game_details = await self.client.get_game_details(appid)
        news_data = await self.client.get_news_for_app(appid, count=count)
        
        if not game_details.get(str(appid), {}).get("data"):
            yield event.plain_result("❌ 未找到该游戏，请确认 AppID 是否正确")
            return
            
        if not news_data.get("appnews", {}).get("newsitems"):
            yield event.plain_result("❌ 未找到该游戏的新闻")
            return
            
        game_name = game_details[str(appid)]["data"]["name"]
        news_items = news_data["appnews"]["newsitems"]
        
        result = [
            Comp.Plain(f"📰 {game_name} 最新新闻\n\n")
        ]
        
        for item in news_items:
            title = item.get("title", "无标题")
            date = datetime.fromtimestamp(item.get("date", 0)).strftime("%Y-%m-%d %H:%M")
            content = item.get("contents", "").replace("\r\n", "\n").replace("\n\n", "\n")
            url = item.get("url", "")
            
            result.append(Comp.Plain(f"【{title}】- {date}\n"))
            result.append(Comp.Plain(f"{content[:200]}...\n"))
            result.append(Comp.Plain(f"详情: {url}\n\n"))
        
        yield event.chain_result(result)
    
    async def handle_deals(self, event: AstrMessageEvent) -> AsyncGenerator:
        """处理 /steam_deals 命令"""
        args = event.message_str.split()
        count = 5
        if len(args) > 1 and "=" in args[1]:
            key, value = args[1].split("=", 1)
            if key == "count":
                try:
                    count = int(value)
                    count = min(max(count, 1), 10)  # 限制在1-10条之间
                except ValueError:
                    pass
        
        # 获取特惠游戏
        featured = await self.client.get_featured_games()
        if not featured.get("specials"):
            yield event.plain_result("❌ 无法获取特惠信息")
            return
            
        specials = featured["specials"][:count]
        
        result = [
            Comp.Plain(f"🔥 Steam 当前特惠游戏 (前{count}款)\n\n")
        ]
        
        for game in specials:
            name = game.get("name", "未知游戏")
            discount = game.get("discount_percent", 0)
            final_price = game.get("final_price", 0) / 100  # 价格单位为分
            original_price = game.get("original_price", 0) / 100
            
            result.append(Comp.Plain(f"【{name}】\n"))
            result.append(Comp.Plain(f"折扣: {discount}% off\n"))
            result.append(Comp.Plain(f"价格: ¥{final_price:.2f} (原价: ¥{original_price:.2f})\n\n"))
        
        yield event.chain_result(result)
    
    async def handle_stats(self, event: AstrMessageEvent) -> AsyncGenerator:
        """处理 /steam_stats 命令"""
        qq_id = event.get_sender_id()
        steamid = self.dao.get_steam_id(qq_id)
        if not steamid:
            yield event.plain_result("❌ 您尚未绑定 Steam ID。请先使用 /steam_bind <steamid> 命令绑定")
            return
        
        # 获取用户信息
        user_data = await self.client.request(
            "ISteamUser", "GetPlayerSummaries", version="v2", steamids=steamid
        )
        players = user_data.get("response", {}).get("players", [])
        if not players:
            yield event.plain_result("❌ 无法获取用户信息")
            return
            
        player = players[0]
        
        # 获取游戏库信息
        games_data = await self.client.get_owned_games(steamid)
        games = games_data.get("response", {}).get("games", [])
        
        # 获取好友列表
        friends_data = await self.client.request("ISteamUser", "GetFriendList", steamid=steamid, relationship="friend")
        friends = friends_data.get("friendslist", {}).get("friends", [])
        
        # 构建统计信息
        personaname = player.get("personaname", "未知用户")
        avatar = player.get("avatarfull", "")
        status = player.get("personastate", 0)
        status_text = ["离线", "在线", "忙碌", "离开", "打盹", "想交易", "想玩游戏"][min(status, 6)]
        
        created_date = self.dao.get_earliest_stats_date(qq_id)
        track_days = "未知" if not created_date else (
            datetime.now() - datetime.strptime(created_date, "%Y-%m-%d")
        ).days
        
        # 构建结果
        result = [
            Comp.Plain(f"📊 Steam 账号统计 - {personaname}\n\n"),
            Comp.Image.fromURL(avatar) if avatar else Comp.Plain(""),
            Comp.Plain(f"账号状态: {status_text}\n"),
            Comp.Plain(f"游戏总数: {len(games)} 款\n"),
            Comp.Plain(f"总游戏时间: {sum(g.get('playtime_forever', 0) for g in games) / 60:.1f} 小时\n"),
            Comp.Plain(f"好友数量: {len(friends)} 人\n"),
            Comp.Plain(f"统计天数: {track_days}\n\n")
        ]
        
        # 添加最近游戏时间变化统计
        stats_rows = self.dao.get_library_stats(qq_id)
        
        if stats_rows:
            recent_stats = [json.loads(row[1]) for row in stats_rows]
            result.append(Comp.Plain("📈 最近游戏时间变化:\n"))
            
            for i, stats in enumerate(recent_stats):
                date = stats_rows[i][0]
                daily_time = stats.get("daily_playtime", 0)
                result.append(Comp.Plain(f"{date}: {daily_time:.1f}小时\n"))
        
        yield event.chain_result(result)
