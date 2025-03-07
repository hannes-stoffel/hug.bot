import time, sys

from beemapi.exceptions import UnhandledRPCError
from BotConfig import BotConfig
from HiveBot import HiveBot


###
### Encapsulating the actual_main in a try except finally block
### Much better readability and this also allows a nice way 
### to get a last minute error messages to be sent to Discord 
### in case something goes wrong.
###

if __name__ == '__main__':
    
    # TODO: Make this a command line parameter
    SQLITE_DATABASE_FILE = 'tipbot.db'
    
    # Load the bot config
    botconfig = BotConfig(SQLITE_DATABASE_FILE)

    # Check if all config lines are set. 
    missing_config_lines = botconfig.populate_table()

    # Any missing config line is now created with a default value. 
    # If that was the case, we stop here, most likely the config needs to be reviewed.
    if (missing_config_lines>0):
        print(f'There were {missing_config_lines} lines missing in the config table.')
        print(f'A config review is strongly suggested!')
        sys.exit()

    # Instantiate the bot
    tipping_bot = HiveBot(botconfig)

    # Several different issues can cause a brief connection loss (e.g. dsl-reconnect)
    # In such an event we pause for 60 seconds and try again.
    # If we get two such errors within 90 seconds we terminate
    last_RPC_Error = time.time()-90
    try:
        while True:
            try:
                tipping_bot.run()
            except UnhandledRPCError as error:
                if (time.time()-last_RPC_Error<90):
                    tipping_bot.to_log(f'RPC Error again. Shutdown.')
                    raise error
                else:
                    tipping_bot.to_log(f'RPC Error. Retry in one minute.')
                    last_RPC_Error = time.time()
                    time.sleep(60)
                    tipping_bot.to_log(f'Back to work...')
            except Exception as error:
                tipping_bot.to_log(f'Something went wrong. Exception: {type(error)}')
                raise error
    finally:
        try:
            tipping_bot.to_log('Bot shutting down!')
        finally:
            botconfig.db_connection.close()


