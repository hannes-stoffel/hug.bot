import sqlite3

class BotConfigNotFound(Exception):
    pass


class BotConfig:
    """ This class provides all configurable attributes of the HIVE bot via getter and setter methods
        so they can be accessed as fields of an object instance of this class.

        In background these are stored and read from a sqlite3 database table as name:value pairs.

        This allows to change the behaviour of the bot from outside the script by changing the
        corresponding values in the database.



            :param str dbfile: sqlite3 database filename

        Note::
            Reading field values for which there is no existing entry in the database will result in
            a BotConfigNotFound Exception!
        """
    
    class HiveTippingLevel:
        balance: float = 0
        calls: int = 0
        tip_recipient: float = 0
        tip_caller: float = 0


    # Name of the table in which our name: value pairs are stored
    CONFIG_TABLE = 'hive_bot_config'
    LEVELS_TABLE = 'tipbot_tipping_levels'

    def __init__(self, dbfile: str):
        self.db_connection = sqlite3.connect(dbfile)
        c = self.db_connection.cursor()
        c.execute(f"CREATE TABLE IF NOT EXISTS {self.CONFIG_TABLE} (name TEXT NOT NULL UNIQUE, value TEXT, PRIMARY KEY(name));")
        c.execute(f"CREATE TABLE IF NOT EXISTS {self.LEVELS_TABLE} (balance REAL NOT NULL, calls INTEGER NOT NULL, tip_recipient REAL NOT NULL, tip_caller REAL NOT NULL);")
        # check if any config levels are set.
        c.execute(f"SELECT count(*) rowcount FROM {self.LEVELS_TABLE};")
        row = c.fetchone()
        rowcount = row[0]
        # if there are no config levels set create sample data
        if (rowcount==0):
            c.execute(f"INSERT OR REPLACE INTO {self.LEVELS_TABLE} (balance,calls,tip_recipient,tip_caller) VALUES (0,1,1,1);")
            c.execute(f"INSERT OR REPLACE INTO {self.LEVELS_TABLE} (balance,calls,tip_recipient,tip_caller) VALUES (1,2,1,1);")
            c.execute(f"INSERT OR REPLACE INTO {self.LEVELS_TABLE} (balance,calls,tip_recipient,tip_caller) VALUES (10,3,1,1);")
            c.execute(f"INSERT OR REPLACE INTO {self.LEVELS_TABLE} (balance,calls,tip_recipient,tip_caller) VALUES (100,4,1,1);")
            c.execute(f"INSERT OR REPLACE INTO {self.LEVELS_TABLE} (balance,calls,tip_recipient,tip_caller) VALUES (500,5,1,1);")
        c.close()
        self.db_connection.commit()


    def get_tipping_level(self, balance: float) -> HiveTippingLevel:
        """ Determines the tipping level for a given balance.
                :param float balance: Given balance for which the tipping level shall be determined

                :returns HiveTippingLevel: Instance of HiveTippingLevel with the data stored in its fields.
        """
        c = self.db_connection.cursor()
        c.execute(f"SELECT max(balance) as balance, calls, tip_recipient, tip_caller FROM {self.LEVELS_TABLE} WHERE balance <= ?;",
                  [balance])
        row = c.fetchone()
        c.close()
        result = BotConfig.HiveTippingLevel()
        if (not row is None):
            result.balance = row[0]
            result.calls = row[1]
            result.tip_recipient = row[2]
            result.tip_caller = row[3]
        return result

    def get_max_tipping_level(self) -> HiveTippingLevel:
        c = self.db_connection.cursor()
        c.execute(
            f"SELECT max(balance) as balance, calls, tip_recipient, tip_caller FROM {self.LEVELS_TABLE};")
        row = c.fetchone()
        c.close()
        result = BotConfig.HiveTippingLevel()
        if (not row is None):
            result.balance = row[0]
            result.calls = row[1]
            result.tip_recipient = row[2]
            result.tip_caller = row[3]
        return result

    def is_no_limit_sender(self, user: str) -> bool:
        return user in self.no_limit_sender

    def get_max_tip(self) -> float:
        c = self.db_connection.cursor()
        c.execute(
            f"select max(tip_caller+tip_recipient) as maxtip from {self.LEVELS_TABLE};")
        row = c.fetchone()
        c.close()
        return float(row[0])

    def get_min_balance(self) -> float:
        c = self.db_connection.cursor()
        c.execute(
            f"select min(balance) as minbalance from {self.LEVELS_TABLE} WHERE calls>0;")
        row = c.fetchone()
        c.close()
        return float(row[0])


    def __get_value(self, name: str):
        """ Generic function to read a value for a given config name from database
                Parameters
                ----------
                    name: str
                        name of the config parameter

                Note
                ----
                    Reading values for which there is no existing entry in the database will result in
                    a BotConfigNotFound Exception!
                """
        c = self.db_connection.cursor()
        c.execute(f"SELECT VALUE FROM {self.CONFIG_TABLE} WHERE UPPER(NAME) = ?;",
                  [name.upper()])
        row = c.fetchone()
        c.close()
        if (row is None):
            raise BotConfigNotFound(name)
        return row[0]

    def __set_value(self, name: str, value: str):
        """ Generic function to write a value for a given config name to database
                
                     :param str name: name of the config parameter
                     :param str value: value of the config parameter

                     .. note:: If the name:value pair does not exist yet it will be created.

                    If the name:value pair already exists, the value will be overwritten.
                 """
        c = self.db_connection.cursor()
        c.execute(
            f'INSERT OR REPLACE INTO {self.CONFIG_TABLE} (name, value) VALUES (?,?);',
            [
                name.upper(),
                value
            ])
        c.close()
        self.db_connection.commit()

    ######################################################
    # account_name                                       #
    ######################################################
    @property
    def account_name(self):
        return self.__get_value('account_name')

    @account_name.setter
    def account_name(self, value: str):
        self.__set_value('account_name', value)

    ######################################################
    # active_key                                         #
    ######################################################
    @property
    def active_key(self):
        return self.__get_value('active_key')

    @active_key.setter
    def active_key(self, value: str):
        self.__set_value('active_key', value)

    ######################################################
    # allow_self_tipping                                 #
    ######################################################
    @property
    def allow_self_tipping(self):
        return self.__get_value('allow_self_tipping').upper()=='TRUE'

    @allow_self_tipping.setter
    def allow_self_tipping(self, value: bool):
        if (value):
            self.__set_value('allow_self_tipping', 'TRUE')
        else:
            self.__set_value('allow_self_tipping', 'FALSE')

    ######################################################
    # app_name                                           #
    ######################################################
    @property
    def app_name(self):
        return self.__get_value('app_name')

    @app_name.setter
    def app_name(self, value: str):
        self.__set_value('app_name', value)

    ######################################################
    # app_name_version                                   #
    ######################################################
    @property
    def app_name_version(self):
        return self.app_name + '/' + self.version

    ######################################################
    # banned_caller                                      #
    ######################################################
    @property
    def banned_caller(self):
        return self.__get_value('banned_caller').replace(' ','').split(',')

    @banned_caller.setter
    def banned_caller(self, value):
        if (type(value) is str):
            self.__set_value('banned_caller', value.replace(' ', ''))
        elif (type(value) is list):
            self.__set_value('banned_caller', ','.join(value).replace(' ', ''))

    ######################################################
    # banned_recipient                                   #
    ######################################################
    @property
    def banned_recipient(self):
        return self.__get_value('banned_recipient').replace(' ','').split(',')

    @banned_recipient.setter
    def banned_recipient(self, value):
        if (type(value) is str):
            self.__set_value('banned_recipient', value.replace(' ', ''))
        elif (type(value) is list):
            self.__set_value('banned_recipient', ','.join(value).replace(' ', ''))

    ######################################################
    # cp_community                                       #
    ######################################################
    @property
    def cp_community(self):
        return self.__get_value('cp_community')

    @cp_community.setter
    def cp_community(self, value: str):
        self.__set_value('cp_community', value)

    ######################################################
    # cp_permlink_prefix                                 #
    ######################################################
    @property
    def cp_permlink_prefix(self):
        return self.__get_value('cp_permlink_prefix')

    @cp_permlink_prefix.setter
    def cp_permlink_prefix(self, value: str):
        self.__set_value('cp_permlink_prefix', value)

    ######################################################
    # cp_tags                                            #
    ######################################################
    @property
    def cp_tags(self):
        return self.__get_value('cp_tags').replace(' ','').split(',')

    @cp_tags.setter
    def cp_tags(self, value):
        if (type(value) is str):
            self.__set_value('cp_tags', value.replace(' ', ''))
        elif (type(value) is list):
            self.__set_value('cp_tags', ','.join(value).replace(' ', ''))

    ######################################################
    # current_block                                      #
    ######################################################
    @property
    def current_block(self):
        return int(self.__get_value('current_block'))

    @current_block.setter
    def current_block(self, value: int):
        self.__set_value('current_block', str(value))

    ######################################################
    # discord_bot_name                                   #
    ######################################################
    @property
    def discord_bot_name(self):
        return self.__get_value('discord_bot_name')

    @discord_bot_name.setter
    def discord_bot_name(self, value: str):
        self.__set_value('discord_bot_name', value)

    ######################################################
    # discord_webhook                                    #
    ######################################################
    @property
    def discord_webhook(self):
        return self.__get_value('discord_webhook')

    @discord_webhook.setter
    def discord_webhook(self, value: str):
        self.__set_value('discord_webhook', value)

    ######################################################
    # enable_collection_post                             #
    ######################################################
    @property
    def enable_collection_post(self):
        return self.__get_value('enable_collection_post').upper()=='TRUE'

    @enable_collection_post.setter
    def enable_collection_post(self, value: bool):
        if (value):
            self.__set_value('enable_collection_post', 'TRUE')
        else:
            self.__set_value('enable_collection_post', 'FALSE')


    ######################################################
    # enable_comments                                    #
    ######################################################
    @property
    def enable_comments(self):
        return self.__get_value('enable_comments').upper()=='TRUE'

    @enable_comments.setter
    def enable_comments(self, value: bool):
        if (value):
            self.__set_value('enable_comments', 'TRUE')
        else:
            self.__set_value('enable_comments', 'FALSE')

    ######################################################
    # enable_discord                                     #
    ######################################################
    @property
    def enable_discord(self):
        return self.__get_value('enable_discord').upper()=='TRUE'

    @enable_discord.setter
    def enable_discord(self, value: bool):
        if (value):
            self.__set_value('enable_discord', 'TRUE')
        else:
            self.__set_value('enable_discord', 'FALSE')

    ######################################################
    # enable_token_transfer                              #
    ######################################################
    @property
    def enable_token_transfer(self):
        return self.__get_value('enable_token_transfer').upper()=='TRUE'

    @enable_token_transfer.setter
    def enable_token_transfer(self, value: bool):
        if (value):
            self.__set_value('enable_token_transfer', 'TRUE')
        else:
            self.__set_value('enable_token_transfer', 'FALSE')

    ######################################################
    # enable_upvote                                      #
    ######################################################
    @property
    def enable_upvote(self):
        return self.__get_value('enable_upvote').upper()=='TRUE'

    @enable_upvote.setter
    def enable_upvote(self, value: bool):
        if (value):
            self.__set_value('enable_upvote', 'TRUE')
        else:
            self.__set_value('enable_upvote', 'FALSE')

    ######################################################
    # hive_api_nodes                                     #
    ######################################################
    @property
    def hive_api_nodes(self):
        return self.__get_value('hive_api_nodes').replace(' ','').split(',')

    @hive_api_nodes.setter
    def hive_api_nodes(self, value):
        if (type(value) is str):
            self.__set_value('hive_api_nodes', value.replace(' ', ''))
        elif (type(value) is list):
            self.__set_value('hive_api_nodes', ','.join(value).replace(' ', ''))

    ######################################################
    # max_commands                                       #
    ######################################################
    @property
    def max_commands(self):
        return int(self.__get_value('max_commands'))

    @max_commands.setter
    def max_commands(self, value: int):
        self.__set_value('max_commands', str(value))

    ######################################################
    # no_limit_sender                                    #
    ######################################################
    @property
    def no_limit_sender(self):
        return self.__get_value('no_limit_sender').replace(' ','').split(',')

    @no_limit_sender.setter
    def no_limit_sender(self, value):
        if (type(value) is str):
            self.__set_value('no_limit_sender', value.replace(' ', ''))
        elif (type(value) is list):
            self.__set_value('no_limit_sender', ','.join(value).replace(' ', ''))

    ######################################################
    # permlink_log_prefix                                #
    ######################################################
    @property
    def permlink_log_prefix(self):
        return self.__get_value('permlink_log_prefix')

    @permlink_log_prefix.setter
    def permlink_log_prefix(self, value: str):
        self.__set_value('permlink_log_prefix', value)

    ######################################################
    # posting_key                                        #
    ######################################################
    @property
    def posting_key(self):
        return self.__get_value('posting_key')

    @posting_key.setter
    def posting_key(self, value: str):
        self.__set_value('posting_key', value)

    ######################################################
    # require_stake                                      #
    ######################################################
    @property
    def require_stake(self):
        return self.__get_value('require_stake').upper()=='TRUE'

    @require_stake.setter
    def require_stake(self, value: bool):
        if (value):
            self.__set_value('require_stake', 'TRUE')
        else:
            self.__set_value('require_stake', 'FALSE')

    ######################################################
    # tip_as_stake                                       #
    ######################################################
    @property
    def tip_as_stake(self):
        return self.__get_value('tip_as_stake').upper()=='TRUE'

    @tip_as_stake.setter
    def tip_as_stake(self, value: bool):
        if (value):
            self.__set_value('tip_as_stake', 'TRUE')
        else:
            self.__set_value('tip_as_stake', 'FALSE')

    ######################################################
    # tip_commands                                       #
    ######################################################
    @property
    def tip_commands(self):
        return self.__get_value('tip_commands').replace(' ','').split(',')

    @tip_commands.setter
    def tip_commands(self, value):
        if (type(value) is str):
            self.__set_value('tip_commands', value.replace(' ', ''))
        elif (type(value) is list):
            self.__set_value('tip_commands', ','.join(value).replace(' ', ''))


    ######################################################
    # token_name                                         #
    ######################################################
    @property
    def token_name(self):
        return self.__get_value('token_name')

    @token_name.setter
    def token_name(self, value: str):
        self.__set_value('token_name', value)

    ######################################################
    # transfer_recipient_memo                            #
    ######################################################
    @property
    def transfer_recipient_memo(self):
        return self.__get_value('transfer_recipient_memo')

    @transfer_recipient_memo.setter
    def transfer_recipient_memo(self, value: str):
        self.__set_value('transfer_recipient_memo', value)

    ######################################################
    # transfer_caller_memo                               #
    ######################################################
    @property
    def transfer_caller_memo(self):
        return self.__get_value('transfer_caller_memo')

    @transfer_caller_memo.setter
    def transfer_caller_memo(self, value: str):
        self.__set_value('transfer_caller_memo', value)

    ######################################################
    # upvote_balance_linear                              #
    ######################################################
    @property
    def upvote_balance_linear(self):
        return self.__get_value('upvote_balance_linear').upper()=='TRUE'

    @upvote_balance_linear.setter
    def upvote_balance_linear(self, value: bool):
        if (value):
            self.__set_value('upvote_balance_linear', 'TRUE')
        else:
            self.__set_value('upvote_balance_linear', 'FALSE')

    ######################################################
    # upvote_baseline                                    #
    ######################################################
    @property
    def upvote_baseline(self):
        return int(self.__get_value('upvote_baseline'))

    @upvote_baseline.setter
    def upvote_baseline(self, value: int):
        self.__set_value('upvote_baseline', str(value))

    ######################################################
    # upvote_minweight                                      #
    ######################################################
    @property
    def upvote_minweight(self):
        return int(self.__get_value('upvote_minweight'))

    @upvote_minweight.setter
    def upvote_minweight(self, value: int):
        self.__set_value('upvote_minweight', str(value))

    ######################################################
    # upvote_weight                                      #
    ######################################################
    @property
    def upvote_weight(self):
        return int(self.__get_value('upvote_weight'))

    @upvote_weight.setter
    def upvote_weight(self, value: int):
        self.__set_value('upvote_weight', str(value))

    ######################################################
    # version                                            #
    ######################################################
    @property
    def version(self):
        return self.__get_value('version')

    @version.setter
    def version(self, value: str):
        self.__set_value('version', value)



   
    def populate_table(self) -> int:
        """ Populates the config table for all parameters with standard or empty values if they are not set.
               
            :return int: Number of parameter lines added to config table.
                        If this is not 0 you should stop and check your config parameters.
        """
        changed = 0
        try:
            tmp=self.account_name
        except BotConfigNotFound:
            self.account_name='hug.bot'
            changed += 1

        try:
            tmp=self.active_key
        except BotConfigNotFound:
            self.active_key=''
            changed += 1

        try:
            tmp=self.allow_self_tipping
        except BotConfigNotFound:
            self.allow_self_tipping=False
            changed += 1

        try:
            tmp=self.app_name
        except BotConfigNotFound:
            self.app_name='hug.bot'
            changed += 1

        try:
            tmp=self.banned_caller
        except BotConfigNotFound:
            self.banned_caller=''
            changed += 1

        try:
            tmp=self.banned_recipient
        except BotConfigNotFound:
            self.banned_recipient=''
            changed += 1

        try:
            tmp=self.cp_community
        except BotConfigNotFound:
            self.cp_community='hive-179927'
            changed += 1

        try:
            tmp=self.cp_permlink_prefix
        except BotConfigNotFound:
            self.cp_permlink_prefix='HUG-Collection'
            changed += 1

        try:
            tmp=self.cp_tags
        except BotConfigNotFound:
            self.cp_tags='HUG,SLOTHBUZZ'
            changed += 1

        try:
            tmp=self.current_block
        except BotConfigNotFound:
            self.current_block=-1
            changed += 1

        try:
            tmp = self.discord_bot_name
        except BotConfigNotFound:
            self.discord_bot_name = 'hug.bot'
            changed += 1

        try:
            tmp = self.discord_webhook
        except BotConfigNotFound:
            self.discord_webhook = ''
            changed += 1

        try:
            tmp=self.enable_collection_post
        except BotConfigNotFound:
            self.enable_collection_post=True
            changed += 1

        try:
            tmp=self.enable_comments
        except BotConfigNotFound:
            self.enable_comments=True
            changed += 1

        try:
            tmp=self.enable_discord
        except BotConfigNotFound:
            self.enable_discord=True
            changed += 1

        try:
            tmp=self.enable_token_transfer
        except BotConfigNotFound:
            self.enable_token_transfer=True
            changed += 1

        try:
            tmp=self.enable_upvote
        except BotConfigNotFound:
            self.enable_upvote=True
            changed += 1

        try:
            tmp=self.hive_api_nodes
        except BotConfigNotFound:
            self.hive_api_nodes='https://api.hive.blog,https://api.deathwing.me,https://hive-api.arcange.eu'
            changed += 1

        try:
            tmp=self.max_commands
        except BotConfigNotFound:
            self.max_commands=5
            changed += 1

        try:
            tmp=self.no_limit_sender
        except BotConfigNotFound:
            self.no_limit_sender='hannes-stoffel,slothlydoesit'
            changed += 1

        try:
            tmp=self.permlink_log_prefix
        except BotConfigNotFound:
            self.permlink_log_prefix='https://peakd.com/'
            changed += 1

        try:
            tmp=self.posting_key
        except BotConfigNotFound:
            self.posting_key=''
            changed += 1

        try:
            tmp=self.require_stake
        except BotConfigNotFound:
            self.require_stake=False
            changed += 1

        try:
            tmp = self.tip_as_stake
        except BotConfigNotFound:
            self.tip_as_stake = False
            changed += 1

        try:
            tmp=self.tip_commands
        except BotConfigNotFound:
            self.tip_commands='!HUG,!Hug,!hug'
            changed += 1

        try:
            tmp=self.token_name
        except BotConfigNotFound:
            self.token_name='HUG'
            changed += 1

        try:
            tmp=self.transfer_recipient_memo
        except BotConfigNotFound:
            self.transfer_recipient_memo='{{sender_account}} shared a hug with you.'
            changed += 1

        try:
            tmp=self.transfer_caller_memo
        except BotConfigNotFound:
            self.transfer_caller_memo='You shared a hug with {{target_account}}'
            changed += 1

        try:
            tmp=self.upvote_balance_linear
        except BotConfigNotFound:
            self.upvote_balance_linear=True
            changed += 1

        try:
            tmp=self.upvote_baseline
        except BotConfigNotFound:
            self.upvote_baseline=90
            changed += 1

        try:
            tmp=self.upvote_minweight
        except BotConfigNotFound:
            self.upvote_minweight=30
            changed += 1

        try:
            tmp=self.upvote_weight
        except BotConfigNotFound:
            self.upvote_weight=50
            changed += 1

        try:
            tmp=self.version
        except BotConfigNotFound:
            self.version='2025.03.06'
            changed += 1

        return changed







