import asyncio
from aiohttp import ClientSession, ClientError
from aiocache import cached, Cache
from aiocache.serializers import JsonSerializer
from astrbot.api import logger

class SteamAPIClient:
    BASE = "https://api.steampowered.com"
    PARTNER = "https://partner.steam-api.com"
    STORE = "https://store.steampowered.com/api"
    MARKET = "https://steamcommunity.com/market"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._session: ClientSession = None

    async def _get_session(self) -> ClientSession:
        """获取或创建会话，复用连接池以提高性能"""
        if not self._session or self._session.closed:
            self._session = ClientSession()
        return self._session

    async def close(self):
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()

    @cached(ttl=300, cache=Cache.MEMORY, serializer=JsonSerializer())
    async def request(self, interface: str, method: str, version: str = "v1", **params) -> dict:
        """
        通用请求，含缓存，默认 5 分钟TTL，防止限流
        
        参数:
            interface: Steam API 接口名，如 ISteamUser
            method: 方法名，如 GetPlayerSummaries
            version: API 版本，默认 v1
            **params: 其他参数
        
        返回:
            字典格式的 API 响应
        """
        url = f"{self.BASE}/{interface}/{method}/{version}/"
        params.update(key=self.api_key)
        session = await self._get_session()
        try:
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                return await resp.json()
        except ClientError as e:
            logger.error(f"Steam API 请求错误: {e}")
            return {}

    async def partner_request(self, interface: str, method: str, version: str = "v4", **params) -> dict:
        """
        Partner API 专用域名，不走缓存
        
        参数:
            interface: Steam Partner API 接口名
            method: 方法名
            version: API 版本，默认 v4
            **params: 其他参数
            
        返回:
            字典格式的 API 响应
        """
        url = f"{self.PARTNER}/{interface}/{method}/{version}/"
        params.update(key=self.api_key)
        session = await self._get_session()
        try:
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                return await resp.json()
        except ClientError as e:
            logger.error(f"Steam Partner API 错误: {e}")
            return {}
    
    @cached(ttl=1800, cache=Cache.MEMORY, serializer=JsonSerializer())
    async def get_achievements(self, steamid: str, appid: int) -> dict:
        """获取玩家在特定游戏中的成就完成情况
        
        参数:
            steamid: 玩家的 Steam 64位ID
            appid: 游戏的 AppID
            
        返回:
            包含游戏和成就信息的字典
        """
        return await self.request("ISteamUserStats", "GetPlayerAchievements", steamid=steamid, appid=appid)
    
    @cached(ttl=1800, cache=Cache.MEMORY, serializer=JsonSerializer())
    async def get_all_achievements(self, appid: int) -> dict:
        """获取游戏的所有成就信息
        
        参数:
            appid: 游戏的 AppID
            
        返回:
            包含游戏所有成就的字典
        """
        return await self.request("ISteamUserStats", "GetSchemaForGame", appid=appid)
    
    @cached(ttl=1800, cache=Cache.MEMORY, serializer=JsonSerializer())
    async def get_owned_games(self, steamid: str) -> dict:
        """获取玩家拥有的游戏列表
        
        参数:
            steamid: 玩家的 Steam 64位ID
            
        返回:
            包含玩家游戏列表的字典
        """
        return await self.request(
            "IPlayerService", 
            "GetOwnedGames", 
            steamid=steamid, 
            include_appinfo=1, 
            include_played_free_games=1
        )
    
    @cached(ttl=3600, cache=Cache.MEMORY, serializer=JsonSerializer())
    async def get_news_for_app(self, appid: int, count: int = 3, max_length: int = 300) -> dict:
        """获取游戏的最新新闻
        
        参数:
            appid: 游戏的 AppID
            count: 返回的新闻条数，默认3条
            max_length: 新闻内容最大长度，默认300字符
            
        返回:
            包含游戏新闻的字典
        """
        return await self.request(
            "ISteamNews", 
            "GetNewsForApp", 
            appid=appid, 
            count=count, 
            maxlength=max_length
        )
    
    @cached(ttl=3600, cache=Cache.MEMORY, serializer=JsonSerializer())
    async def get_game_details(self, appid: int) -> dict:
        """获取游戏详细信息
        
        参数:
            appid: 游戏的 AppID
            
        返回:
            包含游戏详情的字典
        """
        session = await self._get_session()
        try:
            url = f"{self.STORE}/appdetails"
            async with session.get(url, params={"appids": appid}) as resp:
                resp.raise_for_status()
                return await resp.json()
        except ClientError as e:
            logger.error(f"获取游戏详情错误: {e}")
            return {}
    
    @cached(ttl=1800, cache=Cache.MEMORY, serializer=JsonSerializer())
    async def get_market_price(self, appid: int, market_hash_name: str) -> dict:
        """获取 Steam 市场中物品的价格
        
        参数:
            appid: 游戏的 AppID
            market_hash_name: 物品的市场哈希名称
            
        返回:
            包含物品价格信息的字典
        """
        session = await self._get_session()
        try:
            url = f"{self.MARKET}/priceoverview/"
            params = {
                "appid": appid,
                "currency": 23,  # CNY
                "market_hash_name": market_hash_name
            }
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                return await resp.json()
        except ClientError as e:
            logger.error(f"获取市场价格错误: {e}")
            return {}
    
    @cached(ttl=14400, cache=Cache.MEMORY, serializer=JsonSerializer())  # 4小时缓存
    async def get_featured_games(self) -> dict:
        """获取 Steam 商店特色和促销游戏
        
        返回:
            包含特色和促销游戏的字典
        """
        session = await self._get_session()
        try:
            url = f"{self.STORE}/featured"
            async with session.get(url) as resp:
                resp.raise_for_status()
                return await resp.json()
        except ClientError as e:
            logger.error(f"获取特色游戏错误: {e}")
            return {}
