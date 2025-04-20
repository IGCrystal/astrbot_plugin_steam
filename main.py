import asyncio
import json
import time
import os
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
    # 移除CONFIG_SCHEMA，使用自定义配置文件加载

    def __init__(self, context: Context):
        super().__init__(context)
        self.client = None
        self.dao = None
        self.notification = None
        self.handlers = None
        self.task_service = None
        self.scheduler_manager = None
        self.config = {}  # 自定义配置对象
        
    def on_load(self):
        # 加载自定义配置文件
        self.load_config()
        api_key = self.config.get("api_key", "")
        
        if not api_key:
            logger.error("Steam API Key 未配置，插件无法正常工作")
            return
            
        # 初始化 API 客户端和 DAO
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
            self.get_plugin_config
        )
        
        # 初始化调度器管理器
        self.scheduler_manager = SchedulerManager(self.config)
        
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
    
    def load_config(self):
        """加载自定义配置文件"""
        # 使用AstrBot框架的相对路径
        config_dir = "data/plugins_data/astrbot_plugin_steam"
        config_file = f"{config_dir}/config.json"
        
        # 确保配置目录存在
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            logger.info(f"已创建配置目录: {config_dir}")
        
        # 默认配置
        default_config = {
            "api_key": "",
            "check_interval": 60,
            "news_check_interval": 60,
            "discount_check_interval": 8,
            "price_alert_threshold": 15,
            "cache_ttl": 300
        }
        
        # 如果配置文件不存在，创建它
        if not os.path.exists(config_file):
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(default_config, f, ensure_ascii=False, indent=4)
            logger.info(f"已创建默认配置文件: {config_file}")
            self.config = default_config
        else:
            # 读取现有配置
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                logger.info(f"已加载配置文件: {config_file}")
            except Exception as e:
                logger.error(f"加载配置文件时出错: {e}")
                self.config = default_config
    
    def get_plugin_config(self):
        """获取插件配置，供其他组件使用"""
        return self.config
    
    def save_config(self):
        """保存配置到文件"""
        # 使用AstrBot框架的相对路径
        config_file = "data/plugins_data/astrbot_plugin_steam/config.json"
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            logger.info(f"已保存配置到: {config_file}")
            return True
        except Exception as e:
            logger.error(f"保存配置文件时出错: {e}")
            return False
    
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
    
    @filter.command("steam_config")
    async def cmd_config(self, event: AstrMessageEvent):
        """管理插件配置
        
        用法:
          /steam_config set <key> <value> - 设置配置项
          /steam_config get <key> - 获取配置项
          /steam_config list - 列出所有配置
        """
        args = event.message_str.split()
        if len(args) < 2:
            yield event.plain_result("❌ 参数不足，格式: /steam_config <set/get/list> [key] [value]")
            return
            
        action = args[1]
        
        if action == "list":
            # 过滤掉api_key的实际值，避免泄露
            safe_config = self.config.copy()
            if "api_key" in safe_config and safe_config["api_key"]:
                safe_config["api_key"] = "****" + safe_config["api_key"][-4:] if len(safe_config["api_key"]) > 4 else "****"
                
            result = ["当前配置：\n"]
            for key, value in safe_config.items():
                result.append(f"{key}: {value}\n")
                
            yield event.plain_result("".join(result))
            return
            
        if len(args) < 3:
            yield event.plain_result("❌ 请提供配置项名称")
            return
            
        key = args[2]
        
        if action == "get":
            if key not in self.config:
                yield event.plain_result(f"❌ 配置项 {key} 不存在")
                return
                
            # 如果是api_key，隐藏部分内容
            value = self.config[key]
            if key == "api_key" and value:
                value = "****" + value[-4:] if len(value) > 4 else "****"
                
            yield event.plain_result(f"{key}: {value}")
            
        elif action == "set":
            if len(args) < 4:
                yield event.plain_result("❌ 请提供配置值")
                return
                
            value = args[3]
            
            # 尝试转换为正确的数据类型
            if key in ["check_interval", "news_check_interval", "discount_check_interval", "cache_ttl"]:
                try:
                    value = int(value)
                except ValueError:
                    yield event.plain_result(f"❌ {key} 必须是整数")
                    return
            elif key == "price_alert_threshold":
                try:
                    value = float(value)
                except ValueError:
                    yield event.plain_result(f"❌ {key} 必须是数字")
                    return
                    
            # 更新配置
            self.config[key] = value
            
            # 保存配置
            if self.save_config():
                yield event.plain_result(f"✅ 已设置 {key} = {value}")
            else:
                yield event.plain_result("❌ 保存配置失败")
        else:
            yield event.plain_result("❌ 未知操作，支持的操作：set/get/list")
    
    def on_unload(self):
        """插件卸载时关闭会话与调度器"""
        logger.info("Steam Plus 插件正在卸载...")
        if self.scheduler_manager:
            self.scheduler_manager.shutdown(wait=False)
        if self.client:
            asyncio.create_task(self.client.close())
