# Hive Tipping Bot

React to Bot commands (e.g. !HUG) in comments to send a Hive Engine tip token and upvote the post.

**Author**: [Hannes Stoffel](https://peakd.com/@hannes-stoffel)

## Requirements

- Python 3.11
- [hive-engine 0.2.2](https://github.com/holgern/hiveengine)
- [beem 0.24.23](https://github.com/holgern/beem)
- Jinja2 3.1.4
- requests 2.31.0


## Suggested tools

 - [SQLite Browser](https://sqlitebrowser.org/) to inspect and edit the 'tipbot.db' database file.

## Installation

1. Download the latest release.
2. Adjust the templates to your needs.
3. run *python main.py*
4. If the bot starts for the first time it will create the DB file 'tipbot.db', create the tables and populate the config table 'hive_bot_config' with all the parameters needed.
5. Inspect 'hive_bot_config' table and adjust the configuration to your needs.
6. Inspect 'tipbot_tipping_levels' and adjust to your needs.
7. run *python main.py* to start the bot.


## Feature requests and Bug reports

If you want to suggest any feature, feel free to contact me in [Slothbuzz Community Discord](https://discord.gg/Qkx8kpbUJr).

Please report bugs or suggest features through the [GitHub](https://github.com/hannes-stoffel/hug.bot).

## Bot Service

If you want a tipping bot but cannot or don't want to run it yourself, I can do that for you.

Contact me in [Slothbuzz Community Discord](https://discord.gg/Qkx8kpbUJr) 

## License

Hug.Bot is licensed under the [MIT License](https://opensource.org/license/mit).
