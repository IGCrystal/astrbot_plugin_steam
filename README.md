# Steam Plus 插件

![Steam Plus 版本](https://img.shields.io/badge/版本-0.3.0-blue)

<img src="https://count.getloli.com/@:IGCrystal" alt=":IGCrystal" />

为AstrBot提供全方位Steam集成体验的高级插件，支持好友状态监控、游戏新闻推送、特惠通知、成就查询及市场价格监控等功能。

## 功能特色

- 🔔 **好友状态监控**：实时跟踪Steam好友上线和游戏状态
- 📰 **游戏新闻推送**：自动推送已订阅游戏的最新资讯
- 💰 **特惠和促销通知**：第一时间获取Steam特惠信息
- 🏆 **成就统计查询**：查看游戏成就完成情况
- 📊 **游戏库统计**：详细分析您的游戏库数据和游戏时间
- 📈 **市场价格监控**：追踪物品价格变化并设置价格提醒

## 安装指南

1. 确保您已安装并配置好AstrBot
2. 将插件文件夹放置于AstrBot的插件目录下
3. 在AstrBot管理页面启用插件
4. 获取Steam API密钥并在插件配置页填入

## 获取Steam API密钥

1. 访问 [Steam开发者页面](https://steamcommunity.com/dev/apikey)
2. 登录您的Steam账号
3. 填写域名信息（可填写任意有效域名）
4. 获取生成的API密钥并保存

## 配置说明

| 配置项 | 说明 | 默认值 |
|-------|------|-------|
| api_key | Steam API密钥 | (必填) |
| check_interval | 好友状态检查间隔(秒) | 60 |
| news_check_interval | 新闻检查间隔(分钟) | 60 |
| discount_check_interval | 特惠检查间隔(小时) | 8 |
| price_alert_threshold | 价格波动提醒阈值(%) | 15 |
| cache_ttl | API缓存有效期(秒) | 300 |

## 命令列表

### 基础命令

- `/steam_bind <steamid>` - 绑定Steam ID到当前QQ号
- `/steam_stats` - 显示Steam账号统计信息

### 游戏相关命令

- `/steam_games [top]` - 查询游戏库信息，添加top参数可查看游戏时间排行
- `/steam_achievements <appid>` - 查询指定游戏的成就完成情况
- `/steam_news <appid> [count=3]` - 获取指定游戏的最新新闻
- `/steam_deals [count=5]` - 获取当前Steam特惠游戏

### 订阅与监控命令

- `/steam_subscribe add <appid> [news=true] [deals=true]` - 订阅游戏的新闻和特惠信息
- `/steam_subscribe remove <appid>` - 取消订阅
- `/steam_subscribe list` - 列出已订阅的游戏
- `/steam_market watch <appid> <物品哈希名> <期望价格>` - 监控市场物品价格
- `/steam_market unwatch <id>` - 取消市场物品监控
- `/steam_market list` - 列出已监控的物品

### 通知管理命令

- `/steam_notify_group add <群号> [only_game=true] [mute=23:00-07:00]` - 添加群通知
- `/steam_notify_group remove <群号>` - 移除群通知
- `/steam_notify_group list` - 列出当前群通知设置

## 自动化任务

Steam Plus插件包含以下后台自动化任务：

- **好友状态监控**: 定期检查您的Steam好友状态变化并发送通知
- **游戏新闻检查**: 自动获取订阅游戏的最新新闻并推送
- **特惠与促销检查**: 监控您订阅游戏的特惠情况
- **市场价格监控**: 追踪市场物品价格变化
- **游戏库统计**: 每日自动生成游戏库统计数据

## 架构设计

Steam Plus插件采用模块化设计，核心组件包括：

- **DAO层**: 负责数据存取
- **API客户端**: 负责与Steam API通信
- **命令处理器**: 负责处理用户命令
- **任务服务**: 负责定时任务
- **通知服务**: 负责消息发送
- **调度管理器**: 负责任务调度

## 贡献指南

欢迎为Steam Plus插件提供改进建议和代码贡献！

1. Fork本项目
2. 创建您的特性分支: `git checkout -b feature/amazing-feature`
3. 提交您的更改: `git commit -m 'Add some amazing feature'`
4. 推送到分支: `git push origin feature/amazing-feature`
5. 打开一个Pull Request

## 开源许可

本项目基于MIT许可证开源 - 详见 [LICENSE](LICENSE) 文件

## 联系作者

- 作者: IGCrystal
- 项目链接: [https://github.com/IGCrystal/astrbot_plugin_steam](https://github.com/IGCrystal/astrbot_plugin_steam)

*本插件不隶属于Valve或Steam。所有与Steam相关的商标和版权归Valve Corporation所有。*
