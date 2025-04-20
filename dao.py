import json
import time
from typing import List, Dict, Any, Optional, Tuple


class SteamDAO:
    """Steam 数据访问对象，封装所有数据库操作"""
    
    def __init__(self, db):
        """初始化 DAO 对象
        
        Args:
            db: AstrBot 数据库连接对象
        """
        self.db = db
        
    def init_tables(self) -> None:
        """初始化数据库表结构"""
        # 用户绑定表
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS bindings (
            qq_id TEXT PRIMARY KEY, steam_id TEXT NOT NULL
        )""")
        
        # 好友状态表
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS friend_status (
            qq_id TEXT, friend_steamid TEXT, status INTEGER,
            gameinfo TEXT, PRIMARY KEY (qq_id, friend_steamid)
        )""")
        
        # 通知偏好表
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS notify_prefs (
            qq_id TEXT, group_id TEXT, prefs TEXT,
            PRIMARY KEY (qq_id, group_id)
        )""")
        
        # 游戏订阅表
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS game_subscriptions (
            qq_id TEXT, appid INTEGER, 
            news BOOLEAN DEFAULT 1, deals BOOLEAN DEFAULT 1,
            PRIMARY KEY (qq_id, appid)
        )""")
        
        # 市场监控表
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS market_watches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qq_id TEXT, appid INTEGER, 
            market_hash_name TEXT, desired_price REAL,
            last_price REAL, last_check INTEGER
        )""")
        
        # 新闻历史表
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS news_history (
            appid INTEGER, news_id TEXT,
            date INTEGER, sent BOOLEAN DEFAULT 0,
            PRIMARY KEY (appid, news_id)
        )""")
        
        # 游戏库统计表
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS library_stats (
            qq_id TEXT, date TEXT, stats TEXT,
            PRIMARY KEY (qq_id, date)
        )""")
    
    # 用户绑定相关方法
    def bind_steam_id(self, qq_id: str, steam_id: str) -> None:
        """绑定 QQ 号与 Steam ID"""
        self.db.execute(
            "INSERT OR REPLACE INTO bindings (qq_id, steam_id) VALUES (?, ?)",
            (qq_id, steam_id)
        )
    
    def get_steam_id(self, qq_id: str) -> Optional[str]:
        """获取用户绑定的 Steam ID"""
        row = self.db.fetchrow("SELECT steam_id FROM bindings WHERE qq_id=?", (qq_id,))
        return row[0] if row else None
    
    def get_all_bindings(self) -> List[Tuple[str, str]]:
        """获取所有绑定关系（qq_id, steam_id）"""
        return self.db.fetchall("SELECT qq_id, steam_id FROM bindings")
    
    # 好友状态相关方法
    def get_friend_status(self, qq_id: str, friend_steamid: str) -> Optional[Tuple[int, str]]:
        """获取好友状态和游戏信息"""
        return self.db.fetchrow(
            "SELECT status, gameinfo FROM friend_status WHERE qq_id=? AND friend_steamid=?", 
            (qq_id, friend_steamid)
        )
    
    def update_friend_status(self, qq_id: str, friend_steamid: str, status: int, gameinfo: str) -> None:
        """更新好友状态"""
        old = self.get_friend_status(qq_id, friend_steamid)
        if old:
            self.db.execute(
                "UPDATE friend_status SET status=?, gameinfo=? WHERE qq_id=? AND friend_steamid=?",
                (status, gameinfo, qq_id, friend_steamid)
            )
        else:
            self.db.execute(
                "INSERT INTO friend_status (qq_id, friend_steamid, status, gameinfo) VALUES (?,?,?,?)",
                (qq_id, friend_steamid, status, gameinfo)
            )
    
    # 通知偏好相关方法
    def get_notify_prefs(self, qq_id: str) -> List[Tuple[str, str]]:
        """获取用户的通知偏好设置 (group_id, prefs_json)"""
        return self.db.fetchall("SELECT group_id, prefs FROM notify_prefs WHERE qq_id=?", (qq_id,))
    
    def set_notify_prefs(self, qq_id: str, group_id: str, prefs: Dict[str, Any]) -> None:
        """设置通知偏好"""
        self.db.execute(
            "INSERT OR REPLACE INTO notify_prefs (qq_id, group_id, prefs) VALUES (?, ?, ?)",
            (qq_id, group_id, json.dumps(prefs))
        )
    
    def remove_notify_prefs(self, qq_id: str, group_id: str) -> None:
        """移除通知偏好"""
        self.db.execute("DELETE FROM notify_prefs WHERE qq_id=? AND group_id=?", (qq_id, group_id))
    
    # 游戏订阅相关方法
    def get_game_subscriptions(self, qq_id: Optional[str] = None, news_only: bool = False) -> List[Tuple]:
        """获取游戏订阅信息"""
        if news_only:
            # 只获取订阅了新闻的记录
            if qq_id:
                return self.db.fetchall(
                    "SELECT qq_id, appid FROM game_subscriptions WHERE qq_id=? AND news=1", (qq_id,)
                )
            return self.db.fetchall("SELECT qq_id, appid FROM game_subscriptions WHERE news=1")
        
        # 获取所有订阅或特定用户的订阅
        if qq_id:
            return self.db.fetchall(
                "SELECT appid, news, deals FROM game_subscriptions WHERE qq_id=?", (qq_id,)
            )
        return self.db.fetchall("SELECT qq_id, appid, news, deals FROM game_subscriptions")
    
    def get_deals_subscriptions(self) -> List[Tuple[str, int]]:
        """获取特惠订阅信息 (qq_id, appid)"""
        return self.db.fetchall("SELECT qq_id, appid FROM game_subscriptions WHERE deals=1")
    
    def subscribe_game(self, qq_id: str, appid: int, news: bool = True, deals: bool = True) -> None:
        """订阅游戏"""
        self.db.execute(
            "INSERT OR REPLACE INTO game_subscriptions (qq_id, appid, news, deals) VALUES (?, ?, ?, ?)",
            (qq_id, appid, news, deals)
        )
    
    def unsubscribe_game(self, qq_id: str, appid: int) -> None:
        """取消订阅游戏"""
        self.db.execute("DELETE FROM game_subscriptions WHERE qq_id=? AND appid=?", (qq_id, appid))
    
    # 市场监控相关方法
    def get_market_watches(self, qq_id: Optional[str] = None) -> List[Tuple]:
        """获取市场监控记录"""
        if qq_id:
            return self.db.fetchall(
                "SELECT id, appid, market_hash_name, desired_price, last_price FROM market_watches WHERE qq_id=?", 
                (qq_id,)
            )
        return self.db.fetchall(
            "SELECT id, qq_id, appid, market_hash_name, desired_price, last_price FROM market_watches"
        )
    
    def add_market_watch(self, qq_id: str, appid: int, market_hash_name: str, 
                         desired_price: float, last_price: Optional[float] = None) -> int:
        """添加市场监控"""
        self.db.execute(
            """INSERT INTO market_watches 
               (qq_id, appid, market_hash_name, desired_price, last_price, last_check) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (qq_id, appid, market_hash_name, desired_price, last_price, int(time.time()))
        )
        return self.db.lastrowid()
    
    def update_market_price(self, watch_id: int, current_price: float) -> None:
        """更新市场价格"""
        self.db.execute(
            "UPDATE market_watches SET last_price=?, last_check=? WHERE id=?",
            (current_price, int(time.time()), watch_id)
        )
    
    def remove_market_watch(self, watch_id: int, qq_id: str) -> None:
        """移除市场监控"""
        self.db.execute("DELETE FROM market_watches WHERE id=? AND qq_id=?", (watch_id, qq_id))
    
    # 新闻相关方法
    def check_news_sent(self, appid: int, news_id: str) -> Optional[bool]:
        """检查新闻是否已发送"""
        row = self.db.fetchrow(
            "SELECT sent FROM news_history WHERE appid=? AND news_id=?", 
            (appid, news_id)
        )
        return row[0] if row else None
    
    def mark_news_sent(self, appid: int, news_id: str, sent: bool = True) -> None:
        """标记新闻为已发送"""
        exists = self.check_news_sent(appid, news_id)
        if exists is None:
            self.db.execute(
                "INSERT INTO news_history (appid, news_id, date, sent) VALUES (?, ?, ?, ?)",
                (appid, news_id, int(time.time()), sent)
            )
        else:
            self.db.execute(
                "UPDATE news_history SET sent=? WHERE appid=? AND news_id=?",
                (sent, appid, news_id)
            )
    
    # 游戏库统计相关方法
    def get_library_stats(self, qq_id: str, date: Optional[str] = None) -> Any:
        """获取游戏库统计信息"""
        if date:
            return self.db.fetchrow(
                "SELECT stats FROM library_stats WHERE qq_id=? AND date=?",
                (qq_id, date)
            )
        
        return self.db.fetchall(
            "SELECT date, stats FROM library_stats WHERE qq_id=? ORDER BY date DESC LIMIT 7", 
            (qq_id,)
        )
    
    def save_library_stats(self, qq_id: str, date: str, stats: Dict[str, Any]) -> None:
        """保存游戏库统计信息"""
        self.db.execute(
            "INSERT OR REPLACE INTO library_stats (qq_id, date, stats) VALUES (?, ?, ?)",
            (qq_id, date, json.dumps(stats))
        )
    
    def get_earliest_stats_date(self, qq_id: str) -> Optional[str]:
        """获取最早的统计日期"""
        row = self.db.fetchrow(
            "SELECT date FROM library_stats WHERE qq_id=? ORDER BY date ASC LIMIT 1", 
            (qq_id,)
        )
        return row[0] if row else None
