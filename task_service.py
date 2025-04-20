import json
import time
from datetime import datetime, timedelta

from astrbot.api import logger

from .dao import SteamDAO
from .steam_api_client import SteamAPIClient
from .notification_service import NotificationService

class SteamTaskService:
    """Steam 任务服务，封装所有定时任务的业务逻辑"""
    
    def __init__(self, dao: SteamDAO, client: SteamAPIClient, notification_service: NotificationService, get_config):
        """初始化任务服务
        
        Args:
            dao: 数据访问对象
            client: Steam API客户端
            notification_service: 通知服务
            get_config: 获取配置的函数
        """
        self.dao = dao
        self.client = client
        self.notification = notification_service
        self.get_config = get_config
        
    async def monitor_friends(self):
        """定时任务：拉取好友列表并按偏好发送通知"""
        try:
            # 使用 DAO 获取所有绑定
            for qq_id, steamid in self.dao.get_all_bindings():
                data = await self.client.request("ISteamUser", "GetFriendList", steamid=steamid, relationship="friend")
                friends = data.get("friendslist", {}).get("friends", [])
                steamids = [f["steamid"] for f in friends]
                if not steamids: 
                    continue

                summary = (await self.client.request(
                    "ISteamUser", "GetPlayerSummaries", steamids=",".join(steamids), version="v2"
                )).get("response", {}).get("players", [])

                # 使用 DAO 读取群组偏好
                prefs_rows = self.dao.get_notify_prefs(qq_id)

                for p in summary:
                    fsid, state = p["steamid"], p.get("personastate", 0)
                    game = p.get("gameextrainfo", "")
                    
                    # 使用 DAO 获取好友状态
                    old = self.dao.get_friend_status(qq_id, fsid)
                    
                    if old:
                        prev_state, prev_game = old
                    else:
                        prev_state, prev_game = None, ""

                    # 状态变化检测
                    changed = False
                    game_changed = False
                    
                    # 状态变化
                    if prev_state is not None and (state != prev_state):
                        # 从离线到在线
                        if state > 0 and prev_state == 0:
                            changed = True
                    
                    # 游戏变化
                    if prev_game != game and game:
                        game_changed = True
                        
                    # 如果状态或游戏发生变化，发送通知
                    if changed or game_changed:
                        await self.notification.send_friend_status_notification(
                            qq_id, p, game, prefs_rows, changed, game_changed
                        )

                    # 使用 DAO 更新状态
                    self.dao.update_friend_status(qq_id, fsid, state, game)
        except Exception as e:
            logger.error(f"监控好友状态时出错: {e}")
            
    async def check_game_news(self):
        """定时任务：检查订阅游戏的新闻更新"""
        try:
            # 使用 DAO 获取所有新闻订阅
            subscriptions = self.dao.get_game_subscriptions(news_only=True)
            
            for qq_id, appid in subscriptions:
                # 获取游戏新闻
                news_data = await self.client.get_news_for_app(appid, count=3)
                news_items = news_data.get("appnews", {}).get("newsitems", [])
                
                if not news_items:
                    continue
                    
                # 获取游戏名称
                game_details = await self.client.get_game_details(appid)
                game_name = game_details.get(str(appid), {}).get("data", {}).get("name", f"AppID: {appid}")
                
                # 使用 DAO 检查新闻是否已经发送过
                for item in news_items:
                    news_id = item.get("gid", "")
                    exists = self.dao.check_news_sent(appid, news_id)
                    
                    # 如果新闻不存在或未发送，则发送通知
                    if not exists:
                        await self.notification.send_news_notification(qq_id, game_name, item)
                        
                        # 使用 DAO 记录已发送
                        self.dao.mark_news_sent(appid, news_id, True)
                    elif not exists:  # 存在但未发送
                        # 使用 DAO 标记为已发送
                        self.dao.mark_news_sent(appid, news_id, True)
        except Exception as e:
            logger.error(f"检查游戏新闻时出错: {e}")
            
    async def check_game_discounts(self):
        """定时任务：检查游戏特惠和市场物品价格"""
        try:
            # 使用 DAO 获取特惠订阅
            subscriptions = self.dao.get_deals_subscriptions()
            
            # 获取特惠游戏列表
            featured = await self.client.get_featured_games()
            specials = featured.get("specials", [])
            
            # 创建特惠游戏的快速查找表
            discount_map = {game.get("id"): game for game in specials}
            
            for qq_id, appid in subscriptions:
                if str(appid) in discount_map:
                    game = discount_map[str(appid)]
                    await self.notification.send_discount_notification(qq_id, game)
            
            # 使用 DAO 获取市场监控
            watches = self.dao.get_market_watches()
            
            for watch_id, qq_id, appid, hash_name, desired_price, last_price in watches:
                # 获取当前价格
                price_data = await self.client.get_market_price(appid, hash_name)
                
                if not price_data.get("success"):
                    continue
                    
                lowest_price = price_data.get("lowest_price", "")
                if not lowest_price:
                    continue
                    
                # 提取价格数字
                try:
                    current_price = float(lowest_price.replace("¥", "").strip())
                except ValueError:
                    continue
                
                # 使用 DAO 更新最新价格
                self.dao.update_market_price(watch_id, current_price)
                
                # 检查是否达到目标价格
                if current_price <= desired_price and (last_price is None or last_price > desired_price):
                    await self.notification.send_price_target_notification(
                        qq_id, hash_name, current_price, desired_price
                    )
                
                # 检查价格大幅波动
                if last_price is not None:
                    # 计算价格变动百分比
                    price_threshold = self.get_config().get("price_alert_threshold", 15)  # 默认15%
                    
                    if last_price > 0:
                        change_percent = abs(current_price - last_price) / last_price * 100
                        
                        if change_percent >= price_threshold:
                            await self.notification.send_price_change_notification(
                                qq_id, hash_name, current_price, last_price, change_percent
                            )
        except Exception as e:
            logger.error(f"检查游戏特惠时出错: {e}")
            
    async def generate_library_stats(self):
        """定时任务：生成用户游戏库统计信息"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            # 使用 DAO 获取所有绑定
            for qq_id, steamid in self.dao.get_all_bindings():
                # 获取游戏库信息
                games_data = await self.client.get_owned_games(steamid)
                games = games_data.get("response", {}).get("games", [])
                
                if not games:
                    continue
                
                # 使用 DAO 获取昨天的统计数据
                yesterday_stats = self.dao.get_library_stats(qq_id, yesterday)
                
                daily_playtime = 0
                if yesterday_stats:
                    yesterday_data = json.loads(yesterday_stats[0])
                    yesterday_games = {g["appid"]: g["playtime"] for g in yesterday_data.get("games", [])}
                    
                    # 计算每日新增游戏时间
                    for game in games:
                        appid = game.get("appid")
                        current_playtime = game.get("playtime_forever", 0) / 60  # 转为小时
                        previous_playtime = yesterday_games.get(appid, 0)
                        
                        if current_playtime > previous_playtime:
                            daily_playtime += (current_playtime - previous_playtime)
                
                # 生成今天的统计数据
                stats = {
                    "total_games": len(games),
                    "total_playtime": sum(g.get("playtime_forever", 0) for g in games) / 60,
                    "daily_playtime": daily_playtime,
                    "games": [
                        {
                            "appid": g.get("appid"),
                            "name": g.get("name", ""),
                            "playtime": g.get("playtime_forever", 0) / 60
                        }
                        for g in sorted(games, key=lambda x: x.get("playtime_forever", 0), reverse=True)[:20]
                    ]
                }
                
                # 使用 DAO 保存统计数据
                self.dao.save_library_stats(qq_id, today, stats)
        except Exception as e:
            logger.error(f"生成游戏库统计时出错: {e}")
