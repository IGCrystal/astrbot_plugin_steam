import asyncio
import json
import time
from datetime import datetime, timedelta
import pytz  # 恢复使用pytz

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp

from .steam_api_client import SteamAPIClient
from .dao import SteamDAO
from .command_handlers import SteamCommandHandlers
from .task_service import SteamTaskService
from .notification_service import NotificationService
from .scheduler_manager import SchedulerManager

@register(
    "steam_plus",
    "IGCrystal",
    "Steam Plus 插件，支持高级游戏信息、好友状态监控与个性化通知",
    "0.3.0",
    "https://github.com/IGCrystal/astrbot_plugin_steam"
)
class SteamPlusPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.client = None
        self.dao = None
        self.notification = None
        self.handlers = None
        self.task_service = None
        self.scheduler_manager = None
        
    def on_load(self):
        # 获取配置
        config = self.get_config()
        api_key = config.get("api_key", "")
        
        if not api_key:
            logger.error("Steam API Key 未配置，插件无法正常工作")
            return
            
        # 初始化组件（依赖注入）
        self.client = SteamAPIClient(api_key)
        self.dao = SteamDAO(self.db)
        
        # 初始化通知服务
        self.notification = NotificationService(
            self.send_to_user,
            self.send_to_group
        )
        
        # 初始化命令处理器
        self.handlers = SteamCommandHandlers(
            self.dao, 
            self.client,
            self.send_to_user,
            self.send_to_group
        )
        
        # 初始化任务服务
        self.task_service = SteamTaskService(
            self.dao,
            self.client,
            self.notification,
            self.get_config
        )
        
        # 初始化调度器管理器
        self.scheduler_manager = SchedulerManager(config)
        
        # 数据库初始化
        self.dao.init_tables()
        
        # 设置并启动调度器
        self.scheduler_manager.setup_tasks(
            self.task_service.monitor_friends,
            self.task_service.check_game_news,
            self.task_service.check_game_discounts,
            self.task_service.generate_library_stats
        )
        self.scheduler_manager.start()
        
        logger.info("Steam Plus 插件加载完成")
    
    @filter.command("steam_bind")
    async def cmd_bind(self, event: AstrMessageEvent):
        """绑定 Steam ID 到当前 QQ 号
        
        参数:
          steamid: Steam 64位ID
        """
        async for result in self.handlers.handle_bind(event):
            yield result
    
    @filter.command("steam_notify_group")
    async def cmd_notify_group(self, event: AstrMessageEvent):
        """管理群聊通知设置
        
        用法:
          /steam_notify_group add <群号> [only_game=true] [mute=23:00-07:00]
          /steam_notify_group remove <群号>
          /steam_notify_group list
        """
        async for result in self.handlers.handle_notify_group(event):
            yield result
    
    @filter.command("steam_achievements")
    async def cmd_achievements(self, event: AstrMessageEvent):
        """查询玩家在指定游戏中的成就完成情况
        
        用法:
          /steam_achievements <appid>
        """
        async for result in self.handlers.handle_achievements(event):
            yield result
    
    @filter.command("steam_games")
    async def cmd_games(self, event: AstrMessageEvent):
        """查询玩家的游戏库信息
        
        用法:
          /steam_games [top]
        """
        async for result in self.handlers.handle_games(event):
            yield result
    
    @filter.command("steam_subscribe")
    async def cmd_subscribe(self, event: AstrMessageEvent):
        """订阅游戏的新闻和特惠信息
        
        用法:
          /steam_subscribe add <appid> [news=true] [deals=true]
          /steam_subscribe remove <appid>
          /steam_subscribe list
        """
        async for result in self.handlers.handle_subscribe(event):
            yield result
    
    @filter.command("steam_market")
    async def cmd_market(self, event: AstrMessageEvent):
        """监控 Steam 市场物品价格
        
        用法:
          /steam_market watch <appid> <物品市场哈希名> <期望价格>
          /steam_market unwatch <id>
          /steam_market list
        """
        async for result in self.handlers.handle_market(event):
            yield result
    
    @filter.command("steam_news")
    async def cmd_news(self, event: AstrMessageEvent):
        """获取指定游戏的最新新闻
        
        用法:
          /steam_news <appid> [count=3]
        """
        async for result in self.handlers.handle_news(event):
            yield result
    
    @filter.command("steam_deals")
    async def cmd_deals(self, event: AstrMessageEvent):
        """获取 Steam 当前特惠和促销游戏
        
        用法:
          /steam_deals [count=5]
        """
        async for result in self.handlers.handle_deals(event):
            yield result
    
    @filter.command("steam_stats")
    async def cmd_stats(self, event: AstrMessageEvent):
        """显示用户的 Steam 账号统计信息
        
        用法:
          /steam_stats
        """
        async for result in self.handlers.handle_stats(event):
            yield result
    
    def on_unload(self):
        """插件卸载时关闭会话与调度器"""
        logger.info("Steam Plus 插件正在卸载...")
        if self.scheduler_manager:
            self.scheduler_manager.shutdown(wait=False)
        if self.client:
            asyncio.create_task(self.client.close())
