from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Dict, Any, Callable, Awaitable, Optional

from astrbot.api import logger

class SchedulerManager:
    """调度器管理器，负责创建和管理定时任务"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化调度器管理器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.scheduler = AsyncIOScheduler()
        self._initialized = False
    
    def setup_tasks(self, 
                   monitor_friends: Callable[[], Awaitable[None]],
                   check_game_news: Callable[[], Awaitable[None]],
                   check_game_discounts: Callable[[], Awaitable[None]],
                   generate_library_stats: Callable[[], Awaitable[None]]) -> None:
        """设置定时任务
        
        Args:
            monitor_friends: 监控好友状态的任务函数
            check_game_news: 检查游戏新闻的任务函数
            check_game_discounts: 检查游戏特惠的任务函数
            generate_library_stats: 生成游戏库统计的任务函数
        """
        # 从配置中获取间隔时间
        check_interval = self.config.get("check_interval", 60)
        news_check_interval = self.config.get("news_check_interval", 60)
        discount_check_interval = self.config.get("discount_check_interval", 8)
        
        # 添加定时任务
        self.scheduler.add_job(monitor_friends, "interval", seconds=check_interval)
        self.scheduler.add_job(check_game_news, "interval", minutes=news_check_interval)
        self.scheduler.add_job(check_game_discounts, "interval", hours=discount_check_interval)
        self.scheduler.add_job(generate_library_stats, CronTrigger(hour=0, minute=0))
        
        self._initialized = True
        logger.info(f"调度器已设置: 状态监控({check_interval}秒), 新闻({news_check_interval}分钟), 特惠({discount_check_interval}小时)")
        
    def start(self) -> None:
        """启动调度器"""
        if not self._initialized:
            logger.warning("调度器尚未初始化任务，启动前请先调用 setup_tasks")
            return
            
        self.scheduler.start()
        logger.info("调度器已启动")
        
    def shutdown(self, wait: bool = False) -> None:
        """关闭调度器
        
        Args:
            wait: 是否等待所有任务完成
        """
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("调度器已关闭")
            
    @property
    def running(self) -> bool:
        """调度器是否正在运行"""
        return self.scheduler.running
