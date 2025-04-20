import json
from datetime import datetime
import pytz
from typing import Dict, List, Any, Callable, Awaitable, Optional, Tuple

from astrbot.api import logger

class NotificationService:
    """通知服务，负责消息格式化和发送"""
    
    def __init__(self, send_to_user, send_to_group):
        """初始化通知服务
        
        Args:
            send_to_user: 发送私聊消息的函数
            send_to_group: 发送群聊消息的函数
        """
        self.send_to_user = send_to_user
        self.send_to_group = send_to_group
        
    async def send_friend_status_notification(self, 
                                             qq_id: str, 
                                             player_data: Dict[str, Any], 
                                             game: str, 
                                             prefs_rows: List[Tuple[str, str]], 
                                             status_changed: bool = False, 
                                             game_changed: bool = False) -> None:
        """发送好友状态变更通知
        
        Args:
            qq_id: 接收通知的用户QQ
            player_data: 玩家数据
            game: 游戏名称
            prefs_rows: 通知偏好设置
            status_changed: 状态是否有变化
            game_changed: 游戏是否有变化
        """
        # 没有发生变化，不需要通知
        if not status_changed and not game_changed:
            return
            
        fsid = player_data["steamid"]
        player_name = player_data.get("personaname", "未知玩家")
        
        # 根据变化类型确定通知内容
        if game and game_changed:
            msg = f"🎮 好友 {player_name} 开始游玩：{game}"
        elif game and status_changed:
            msg = f"🎮 好友 {player_name} 正在游玩：{game}"
        elif status_changed:
            msg = f"🔔 好友 {player_name} 已上线"
        else:
            return
            
        # 发送私聊通知
        await self.send_to_user(qq_id, msg)
        
        # 发送群聊通知（根据偏好过滤）
        await self._send_group_notifications(fsid, game, prefs_rows, msg)
    
    async def send_news_notification(self, 
                                   qq_id: str, 
                                   game_name: str, 
                                   news_item: Dict[str, Any]) -> None:
        """发送游戏新闻通知
        
        Args:
            qq_id: 接收通知的用户QQ
            game_name: 游戏名称
            news_item: 新闻数据
        """
        title = news_item.get("title", "无标题")
        date = datetime.fromtimestamp(news_item.get("date", 0)).strftime("%Y-%m-%d %H:%M")
        content = news_item.get("contents", "").replace("\r\n", "\n").replace("\n\n", "\n")
        url = news_item.get("url", "")
        
        message = (
            f"📰 {game_name} 新闻更新\n\n"
            f"【{title}】- {date}\n"
            f"{content[:200]}...\n"
            f"详情: {url}"
        )
        
        await self.send_to_user(qq_id, message)
    
    async def send_discount_notification(self, 
                                       qq_id: str, 
                                       game_data: Dict[str, Any]) -> None:
        """发送游戏折扣通知
        
        Args:
            qq_id: 接收通知的用户QQ
            game_data: 游戏数据，包含价格和折扣信息
        """
        name = game_data.get("name", "未知游戏")
        discount = game_data.get("discount_percent", 0)
        final_price = game_data.get("final_price", 0) / 100
        original_price = game_data.get("original_price", 0) / 100
        
        message = (
            f"🔥 您关注的游戏正在特惠!\n\n"
            f"【{name}】\n"
            f"折扣: {discount}% off\n"
            f"特惠价: ¥{final_price:.2f} (原价: ¥{original_price:.2f})"
        )
        
        await self.send_to_user(qq_id, message)
    
    async def send_price_target_notification(self, 
                                           qq_id: str, 
                                           item_name: str, 
                                           current_price: float, 
                                           target_price: float) -> None:
        """发送物品价格达到目标的通知
        
        Args:
            qq_id: 接收通知的用户QQ
            item_name: 物品名称
            current_price: 当前价格
            target_price: 目标价格
        """
        message = (
            f"💰 物品价格提醒\n\n"
            f"物品: {item_name}\n"
            f"当前价格: ¥{current_price:.2f}\n"
            f"目标价格: ¥{target_price:.2f}\n"
            f"价格已达到或低于您设定的目标!"
        )
        
        await self.send_to_user(qq_id, message)
    
    async def send_price_change_notification(self, 
                                           qq_id: str, 
                                           item_name: str, 
                                           current_price: float, 
                                           previous_price: float, 
                                           change_percent: float) -> None:
        """发送物品价格变动的通知
        
        Args:
            qq_id: 接收通知的用户QQ
            item_name: 物品名称
            current_price: 当前价格
            previous_price: 之前价格
            change_percent: 变动百分比
        """
        change_type = "上涨" if current_price > previous_price else "下跌"
        
        message = (
            f"📊 物品价格大幅波动\n\n"
            f"物品: {item_name}\n"
            f"当前价格: ¥{current_price:.2f}\n"
            f"之前价格: ¥{previous_price:.2f}\n"
            f"变动: {change_percent:.1f}% {change_type}"
        )
        
        await self.send_to_user(qq_id, message)
    
    async def _send_group_notifications(self, 
                                      friend_id: str, 
                                      game: str, 
                                      prefs_rows: List[Tuple[str, str]], 
                                      message: str) -> None:
        """根据用户偏好设置发送群聊通知
        
        Args:
            friend_id: 好友的Steam ID
            game: 游戏名称
            prefs_rows: 通知偏好设置
            message: 要发送的消息
        """
        for gid, prefs in prefs_rows:
            try:
                cfg = json.loads(prefs)
                # 是否只通知游戏状态
                if cfg.get("only_game") and not game:
                    continue
                # 是否在特定好友名单内
                if cfg.get("friends") and friend_id not in cfg["friends"]:
                    continue
                # 检查静音时段
                if self._is_muted_time(cfg.get("mute", [])):
                    continue
                
                await self.send_to_group(gid, message)
            except Exception as e:
                logger.error(f"发送群组通知时出错: {e}")
    
    def _is_muted_time(self, mute_ranges: List[str]) -> bool:
        """检查当前时间是否在静音时段内
        
        Args:
            mute_ranges: 静音时段列表，格式如 ["23:00-07:00"]
            
        Returns:
            bool: 是否在静音时段内
        """
        if not mute_ranges:
            return False
            
        current_time = datetime.now(pytz.timezone('Asia/Shanghai')).time()
        
        for mute_range in mute_ranges:
            try:
                start, end = mute_range.split("-")
                start_time = datetime.strptime(start, "%H:%M").time()
                end_time = datetime.strptime(end, "%H:%M").time()
                
                # 判断当前时间是否在静音时段内
                if start_time <= current_time <= end_time:
                    return True
            except Exception:
                continue
                
        return False
