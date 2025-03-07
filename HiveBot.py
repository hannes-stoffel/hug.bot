import sqlite3
import time
from datetime import datetime, date, timedelta

import beem.instance
import jinja2
from beem.blockchain import Blockchain
from beem.comment import Comment
from beem.exceptions import VotingInvalidOnArchivedPost
from beem.hive import Hive
from beem.utils import sanitize_permlink

import HiveBotUtils
from BotConfig import BotConfig

from beem.account import Account
from hiveengine.wallet import Wallet

import re
import requests


class HiveBot:
    """ This class provides the HIVE bot functionality.
                Create an instance with a valid config, then call the run() method to start the bot loop.

                    :param BotConfig config: An Instance of BotConfig

                .. Note:: All the necessary tables will be created if necessary when the first Object instance is initiated. 

        """
    SQLITE_CALLS_TABLE = 'tipbot_calls'
    SQLITE_VOTES_TABLE = 'tipbot_votes'
    SQLITE_COLLECTIONPOSTS_TABLE = 'tipbot_collectionposts'
    SQLITE_NO_MENTION = 'tipbot_no_mention'

    ##
    ## Reason Codes whether a call was successful
    ##
    RC_SUCCESS = 1
    RC_NO_STAKE = 2
    RC_DAILY_LIMIT = 3
    RC_TOO_MANY_COMMANDS = 4
    RC_SELF_TIPPING = 5
    RC_BOT_TIPPING = 6
    RC_TRANSFER_DISABLED = 80
    RC_BANNED_RECIPIENT = 98
    RC_BANNED_CALLER = 99
    RC_TOTAL = -1
    RC_FAIL = -2

    DEBUG_MODE = False

    
    def __init__(self, config: BotConfig):
        self.config = config

        ### Regex to search for bot commands in the comments
        ### Used to find out how many (other?) commands are in that one comment.
        self.regex_command_pattern = re.compile("[!][a-zA-Z]{3,15}")

        

        keys=[]
        if (self.config.active_key==''):
            # Cannot transfer without active key, so override that setting
            print(f'No Active Key given. Transfers and Voting disabled!')
            self.config.enable_token_transfer = False
            self.config.enable_upvote = False
        else:
            keys.append(self.config.active_key)

        if (self.config.posting_key==''):
            # Cannot comment without posting key, so override that setting
            print(f'No Posting Key given. Comments and Posting disabled!')
            self.config.enable_comments = False
            self.config.enable_collection_post = False
        else:
            keys.append(self.config.posting_key)

        
        
        # Without keys we can still connect in read only mode and listen to what's happening.
        if (len(keys) == 0):
            self.HIVE = Hive(node=config.hive_api_nodes)
        else:
            self.HIVE = Hive(node=config.hive_api_nodes, keys=keys)

        # Important: We need to make sure every call uses the same Blockchain instance
        beem.instance.set_shared_blockchain_instance(self.HIVE)

        # Instantiate Wallet and Account Objects
        self.hive_wallet = Wallet(self.config.account_name)
        self.hive_account = Account(self.config.account_name)

        # Check for the database tables to be ready
        c = self.config.db_connection.cursor()
        c.execute(f"CREATE TABLE IF NOT EXISTS {self.SQLITE_CALLS_TABLE} (datum TEXT NOT NULL, invoker TEXT NOT NULL, recipient TEXT NOT NULL, block_num INTEGER NOT NULL, permlink TEXT NOT NULL, target_permlink TEXT NOT NULL, successRC INTEGER NOT NULL, sent_recipient NUMERIC NOT NULL, sent_caller NUMERIC NOT NULL);")
        c.execute(f"CREATE TABLE IF NOT EXISTS {self.SQLITE_VOTES_TABLE} (datum TEXT NOT NULL, permlink TEXT NOT NULL, weight INTEGER NOT NULL);")
        c.execute(f"CREATE TABLE IF NOT EXISTS {self.SQLITE_COLLECTIONPOSTS_TABLE} (datum TEXT NOT NULL, permlink TEXT NOT NULL);")
        c.execute(f"CREATE TABLE IF NOT EXISTS {self.SQLITE_NO_MENTION} (datum TEXT NOT NULL, user TEXT NOT NULL, permlink TEXT NOT NULL);")
        c.close()
        self.config.db_connection.commit()


    def post_discord_message(self, message_body: str) -> bool:
        """ Sends out a Discord message via webhook provided by config. 
            If Discord messages are disabled in config, exits immediately"""
        if (not self.config.enable_discord):
            return False

        payload = {
            "username": self.config.discord_bot_name,
            "content": message_body
        }

        # Don't let the bot crash if Discord cannot be reached.
        try:
            requests.post(self.config.discord_webhook, data=payload)
            return True
        except Exception as exception:
            print(f"Error while sending discord message:\n{exception}")
            return False

    def to_log(self, message: str):
        """ Writes the log message with a timestamp to console. 
            If Discord is enabled it also sends out a Discord message.
            As Discord provides a timesamp in their app that message is without a timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{timestamp} - {message}")
        if (self.config.enable_discord):
            self.post_discord_message(message)

    def to_debug(self, message: str):
        """ Writes the log message to console only. Adds a timestamp to the output."""
        if (self.DEBUG_MODE):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"DEBUG: {timestamp} - {message}")


    def permlink_processed(self, author: str, permlink: str) -> bool:
        """ Checks whether a comment has already been processed.
            :param str author: The author of the message
            :param str permlink: The permlink of the message
            
            :returns bool: True if a record for that comment already exists in the database marking it as already processed."""
        c = self.config.db_connection.cursor()

        c.execute(f"SELECT count(*) FROM {self.SQLITE_CALLS_TABLE} WHERE permlink = ? AND invoker = ?;" , [permlink, author])
        row = c.fetchone()
        c.close()

        return row[0]!=0

    ## Whenever we process a bot command we store the information in the database.
    def save_action(self, datum, invoker, recipient, block_num, permlink, target_permlink, success, sent_recipient, sent_caller):
        """ Adds a row to the calls table indicating a processed comment and the action taken."""
        c = self.config.db_connection.cursor()

        c.execute(f'INSERT INTO {self.SQLITE_CALLS_TABLE} (datum, invoker, recipient, block_num, permlink, target_permlink, successRC, sent_recipient, sent_caller) VALUES (?,?,?,?,?,?,?,?,?);', [
            datum,
            invoker,
            recipient,
            block_num,
            permlink,
            target_permlink,
            success,
            sent_recipient,
            sent_caller
            ])
        c.close()
        self.config.db_connection.commit()

   
    def get_call_count(self, datum, successRC) -> int:
        """ Returns the number of rows in the calls table for a given data with the specified successRC. 
            
            Use RC_TOTAL to get all the calls of a day without filtering for successRC
            
            User RC_FAIL to get all the calls of a day that failed for any reason i.e. was not RC_SUCCESS"""
        c = self.config.db_connection.cursor()
        if (successRC==self.RC_TOTAL):
            c.execute(f"SELECT count(*) FROM {self.SQLITE_CALLS_TABLE} WHERE DATUM=?;", [datum])
        elif (successRC==self.RC_FAIL):
            c.execute(f"SELECT count(*) FROM {self.SQLITE_CALLS_TABLE} WHERE DATUM=? AND SUCCESSRC<>?;", [datum, self.RC_SUCCESS])
        else:
            c.execute(f"SELECT count(*) FROM {self.SQLITE_CALLS_TABLE} WHERE DATUM=? AND SUCCESSRC=?;", [datum, successRC])
        row = c.fetchone()

        c.close()

        return int(row[0])

    
    def save_vote_action(self, datum, permlink, weight):
        """ Adds a row to votes table indicating that a vote has been cast on a comment."""
        c = self.config.db_connection.cursor()

        c.execute(f'INSERT INTO {self.SQLITE_VOTES_TABLE} (datum, permlink, weight) VALUES (?,?,?);', [
            datum,
            permlink,
            weight
        ])
        c.close()
        self.config.db_connection.commit()

    def get_usercalls_by_date(self, user, datum) -> int:
        """ Determine how many successfull calls a user already made on a given date."""
        c = self.config.db_connection.cursor()

        c.execute(f"SELECT count(*) FROM {self.SQLITE_CALLS_TABLE} WHERE invoker = ? AND DATUM=? AND SUCCESSRC=?;", [user, datum, self.RC_SUCCESS])
        row = c.fetchone()

        c.close()

        return int(row[0])

    def save_collection_post(self, datum, permlink):
        """ Saves the permlink of the collection post for a given date to database. 
            This is easier to retrieve for further calls than querying Hive for it."""
        c = self.config.db_connection.cursor()

        c.execute(f'INSERT INTO {self.SQLITE_COLLECTIONPOSTS_TABLE} (datum, permlink) VALUES (?,?);', [
            datum,
            permlink
        ])
        c.close()
        self.config.db_connection.commit()

    def has_voted(self, permlink) :
        """ Check if there's a row in the votes table indicating we already cast a vote on a comment."""
        c = self.config.db_connection.cursor()

        c.execute(f"SELECT count(*) FROM {self.SQLITE_VOTES_TABLE} WHERE permlink = ?;", [permlink])
        row = c.fetchone()

        c.close()

        return int(row[0])>0


    def post_comment(self, parent_permlink, message) -> bool:
        """ Posts a comment to a post/comment.
            If the original post/comment is not yet processed by the node we might get an exception
            for commenting on something that does not exist. So we need to give them some time.
            At the moment it's set to 1 minute and retrying every 10 seconds.
            """
        success=False
        for i in range(0, 6):
            try:
                self.HIVE.post(
                title='',
                body=message,
                author=self.config.account_name,
                reply_identifier=parent_permlink,
                app=self.config.app_name_version,
                parse_body=True)
                # If we reach this line there was no exception and the comment has been posted.
                success = True
                break
            except Exception as err:
                print(f'Cannot post comment to {parent_permlink} - Exception: {type(err)} - try again in 10 seconds.')
                time.sleep(10)
        return success

    def upvote(self, permlink, weight) -> bool:
        """ Upvote a post. 
        
            :param str permlink: The post to be upvoted. If the permlink is to a comment (not a post) the upvote is skipped.
            :param int weight: Weight of the vote in % 
            :returns bool: True if a vote was cast."""
        comment = Comment(permlink)

        if not comment.is_main_post():
            self.to_log(f"--- Parent post is not a main post. Skipping upvote.")
            return False

        # If it's not pending we cannot vote
        if not comment.is_pending():
            self.to_log(f"--- Cannot upvote {permlink}: not pending anymore.")
            return False

        try:
            comment.upvote(weight, voter=self.config.account_name)
            self.save_vote_action(date.today(), permlink, weight)
            self.to_log(f"--- Upvote sent.")
            return True
        except VotingInvalidOnArchivedPost as err:
            self.to_log(f"--- Cannot upvote {permlink}: not pending anymore.")
        except Exception as err:
            self.to_log(f"--- Cannot upvote {permlink} --- Exception: {type(err)}")
        return False

    ###
    ### Creates the collection post and saves the link into Database
    ### Does NOT check if the post already exists!
    ###
    def create_collectionpost(self, datum=None) -> str:
        """ Creates the collection post and saves the link to database.
            
            Does **NOT** check if the post already exists!
            
            :param date datum: Date for which a collection post shall be created. If set to none or not provided defaults to current date.
            
            :returns str: permlink to the created post."""

        # Create all the parameters for the posting
        if datum is None:
            datum = date.today()
        title = f'{self.config.cp_permlink_prefix}-{datum}'
        permlink = sanitize_permlink(title)
        tags = ','.join(self.config.cp_tags)
        community = self.config.cp_community
        author = self.config.account_name
        datum_yesterday = datum-timedelta(days=1)

        # Get the data to pass to the template.
        total_calls_yesterday = self.get_call_count(datum_yesterday, self.RC_TOTAL)
        successful_calls_yesterday = self.get_call_count(datum_yesterday, self.RC_SUCCESS)
        daily_limit_yesterday = self.get_call_count(datum_yesterday, self.RC_DAILY_LIMIT)
        too_many_commands_yesterday = self.get_call_count(datum_yesterday, self.RC_TOO_MANY_COMMANDS)

        # Get the collection post template.
        collectionpost_template = jinja2.Template(
            open(file='collection_post.template', mode='r', encoding='utf-8').read())

        # Create the post body
        body = collectionpost_template.render(yesterday=datum_yesterday,
                                              total_calls=total_calls_yesterday,
                                              successful_calls=successful_calls_yesterday,
                                              failed_daily_limit=daily_limit_yesterday,
                                              failed_too_many_commands=too_many_commands_yesterday)

        # Inform to Discord and create the post
        self.to_log(f'+++ Creating collection post {title}')
        self.HIVE.post(title=title,
                  body=body,
                  author=author,
                  permlink=permlink,
                  community=community,
                  app=self.config.app_name_version,
                  tags=tags)

        # check for success
        comment = None
        for i in range(10):
            time.sleep(6)
            try:
                comment = Comment(f'@{author}/{permlink}')
                break
            except:
                pass

        if comment is None:
            self.to_log('+++ Failed to create collection post!')
            raise Exception('Failed to create collection post!')

        else:
            self.to_log(f'+++ Success: {self.config.permlink_log_prefix}@{author}/{permlink}')
            self.save_collection_post(datum, permlink)

        return f'@{author}/{permlink}'

    ###
    ### Get the permlink for the collection post of a given date
    ###
    def get_collectionpost(self, datum) -> str:
        """ Get the permlink for the collection post of a given date.
        
            If the post does not exist yet, it will be created."""
        c = self.config.db_connection.cursor()

        c.execute(f"SELECT permlink FROM {self.SQLITE_COLLECTIONPOSTS_TABLE} WHERE datum = ?;",
                  [datum])

        row = c.fetchone()

        if row:
            result = f'@{self.config.account_name}/{row[0]}'
        else:
            result = self.create_collectionpost(datum)

        c.close()

        return result

    def allowed_to_tag(self, user) -> bool:
        """ Checks the database if the user did opt-out of being tagged."""
        c = self.config.db_connection.cursor()

        c.execute(f"SELECT COUNT(*) FROM {self.SQLITE_NO_MENTION} WHERE user = ?;",
                  [user])

        row = c.fetchone()

        result = int(row[0]==0)

        c.close()

        return result

    def disallow_mentions(self, user, datum, permlink):
        """ Creates an entry to database (if it does not exist yet) for the user not to be tagged in comments and posts by the bot"""
        if not self.allowed_to_tag(user):
            # already in database
            return

        c = self.config.db_connection.cursor()

        c.execute(f'INSERT INTO {self.SQLITE_NO_MENTION} (datum, user, permlink) VALUES (?,?,?);', [
            datum,
            user,
            permlink
        ])
        c.close()
        self.config.db_connection.commit()

    def allow_mentions(self, user):
        """ Removes the entry from database (if it exists) of users who don't want to be tagged. """
        if self.allowed_to_tag(user):
            return

        c = self.config.db_connection.cursor()

        c.execute(f'DELETE FROM {self.SQLITE_NO_MENTION} WHERE USER= ?;', [
            user
        ])
        c.close()
        self.config.db_connection.commit()

    def add_tagging_symbol(self, user: str) -> str:
        """ If the user did not opt-out from being tagged returns the username with leading @ for tagging.
            If the user did opt-out from being tagged, returns the username without @ and
            removes the leading @ if it is already there
            
            :param str user: Username to check if they did opt-out from being tagged. Can be called with or without leading @ already in there.
            
            :returns str: Username with or without @ depending on whether the user did opt-out from being tagged in comments/posts by the bot."""
        if self.allowed_to_tag(user.replace('@', '')):
            return f"@{user.replace('@', '')}"
        else:
            return user.replace('@', '')

    def post_collection_comment(self, datum, message) -> bool:
        """ Posts a comment to the bot's collection post for the given datum."""
        try:
            collectionpermlink = self.get_collectionpost(datum)
            return self.post_comment(collectionpermlink, message)
        except Exception as err:
            self.to_log(f"--- Cannot append to daily collection --- Exception: {type(err)}")
            return False

    def bot_has_funds(self) -> bool:
        """ Checks if the bot has enough funds to perform the highest possible tip call."""
        self.hive_wallet.refresh()
        wallet_token_info = self.hive_wallet.get_token(self.config.token_name)

        if not wallet_token_info:
            ## If that happens, we're in deep shit anyway.
            ## But let the calling function take care of that
            balance = 0
        else:
            balance = float(wallet_token_info['balance'])

        # To be on the save side we check against maximum tipped amount
        return balance >= self.config.get_max_tip()

    def process_comment_operation(self, operation):
        """ Process a comment on the blockchain. 
            
            :param dict operation: The raw operation data to be processed"""
        
        # Check if it's really a comment operation
        if (operation['type']!='comment'):
            return

        # Get the relevant information into easier to read variables
        author = operation['author']
        parent_author = operation['parent_author']
        permlink = operation['permlink']
        parent_permlink = operation['parent_permlink']
        block_num = operation['block_num']

        # Process the date from the block. 
        # That way we can process several different dates within one day after not running
        # for a while without the users running into daily limitations because of the bot's downtime.
        datum = operation['timestamp'].date()
        token_name = self.config.token_name

        # I've never seen author been blank but better check to be sure.
        # parent_author is sometimes blank, when a post to a community is treated as a comment
        if (author == '' or parent_author == ''):
            self.to_debug(f'either author={author} or parent_author={parent_author} is empty so nothing to do.')
            return

        # Ignore whatever the bot itself publishes to avoid loops in the comments
        if (author == self.config.account_name):
            self.to_debug(f'Comment by the botaccount {author}. Skipping further processing.')
            return

        # someone is responding to us. Check if the mention should be removed
        if (parent_author == self.config.account_name):
            if (operation['body'].strip().upper() == 'STOP'):
                self.to_log(f'{author} does not want to be mentioned anymore.')
                self.disallow_mentions(author, datum, f'@{author}/{permlink}')
                self.to_log(f'--- written to db')
                return
            elif (operation['body'].strip().upper() in ('TAGME', 'TAG ME')):
                self.to_log(f'{author} wants to allow mentions again.')
                self.allow_mentions(author)
                self.to_log(f'--- written to db')
                return

        # How many and which commands are in there?
        command_list = self.regex_command_pattern.findall(operation['body'])


        trigger_bot = False

        # check every possible bot command against every command found in the comment
        for botcommand in self.config.tip_commands:
            if (botcommand in command_list):
                trigger_bot = True
                break

        # If none of the bot commands is in there we can move on
        if (not trigger_bot):
            return

        # If we made it this far, someone wants to send some tokens.
        self.to_log(f'{author} wants to send {parent_author} some tokens: {self.config.permlink_log_prefix}@{author}/{permlink}')

        # Check if we already processed that one
        if (self.permlink_processed(author, permlink)):
            self.to_log('--- already handled')
            return

        # No tipping the bot
        if (parent_author == self.config.account_name):
            self.to_log(f'--- {author} wants to tip the bot. Not allowed.')
            self.save_action(datum, author, parent_author, block_num, permlink, parent_permlink, self.RC_BOT_TIPPING, 0, 0)
            return

        # If self tipping is not allowed we need to check for that
        if ((self.config.allow_self_tipping == False) and (author == parent_author)):
            self.to_log(f'--- {author} wants to tip themselves. Not allowed.')
            self.save_action(datum, author, parent_author, block_num, permlink, parent_permlink, self.RC_SELF_TIPPING, 0, 0)
            return

        # check for banned authors
        if (author in self.config.banned_caller):
            self.to_log(f'--- {author} is banned from tipping. Not allowed.')
            self.save_action(datum, author, parent_author, block_num, permlink, parent_permlink, self.RC_BANNED_CALLER, 0, 0)
            return

        # check for banned recipients
        if (parent_author in self.config.banned_recipient):
            self.to_log(f'--- {parent_author} is banned from recieving tips. Not allowed.')
            self.save_action(datum, author, parent_author, block_num, permlink, parent_permlink, self.RC_BANNED_RECIPIENT, 0, 0)
            return

        # check how many other commands are in there and if we exceed maximum allowed commands
        max_commands_allowed = self.config.max_commands
        if (max_commands_allowed > 0):
            if (len(command_list) > max_commands_allowed):
                self.to_log(f'--- Overall {len(command_list)} commands: {command_list} but only {max_commands_allowed} allowed. Ignoring call!')
                self.save_action(datum, author, parent_author, block_num, permlink, parent_permlink, self.RC_TOO_MANY_COMMANDS, 0, 0)
                return


        if (author in self.config.no_limit_sender):
            tipping_level = self.config.get_max_tipping_level()
        else:
            if (self.config.require_stake):
                tipping_level = self.config.get_tipping_level(HiveBotUtils.get_staked_balance(author, token_name))
            else:
                tipping_level = self.config.get_tipping_level(HiveBotUtils.get_liquid_balance(author, token_name))

        if (tipping_level.calls==0):
            # Level.calls at 0 means we can stop here, user does not meet minimum requirements
            self.to_log(f'--- {author} does not meet minimum requirements.')
            # post the comment
            if (self.config.enable_comments):
                # Get the comment template.
                comment_no_stake_template = jinja2.Template(open(file='comment_no_stake.template', mode='r', encoding='utf-8').read())
                comment_body = comment_no_stake_template.render(token_name=token_name, target_account=self.add_tagging_symbol(parent_author),
                                                                   sender_account=self.add_tagging_symbol(author),
                                                                   min_staked=float(self.config.get_min_balance()))
                if self.config.enable_collection_post:
                    self.post_collection_comment(datum, comment_body)
                    self.to_log('--- Comment appended to daily collection.')
                elif (self.post_comment(f'@{author}/{permlink}', comment_body)):
                    self.to_log('--- Comment sent.')
                else:
                    self.to_log('--- Could not post comment. Moving on.')


            self.save_action(datum, author, parent_author, block_num, permlink, parent_permlink, self.RC_NO_STAKE, 0, 0)
            return

        # get the number of calls the author already made today
        # if the author is a no limit sender, we treat every call as the first call of the day
        if (author in self.config.no_limit_sender):
            calls_today = 0
        else:
            calls_today = self.get_usercalls_by_date(author, datum)

        if (calls_today>=tipping_level.calls):
            self.to_log(f'--- {author} has reached daily limit of {tipping_level.calls}. No tip sent.')
            # sent the comment
            if (self.config.enable_comments):
                # Get the comment templates. 
                comment_daily_limit_template = jinja2.Template(open(file='comment_daily_limit.template', mode='r', encoding='utf-8').read())
                comment_body = comment_daily_limit_template.render(token_name=token_name, target_account=self.add_tagging_symbol(parent_author),
                                                               sender_account=self.add_tagging_symbol(author),
                                                               today_tips_count=calls_today,
                                                               max_daily_tips=tipping_level.calls)
                if self.config.enable_collection_post:
                    if self.post_collection_comment(datum, comment_body):
                        self.to_log('--- Comment appended to daily collection.')
                elif (self.post_comment(f'@{author}/{permlink}', comment_body)):
                    self.to_log('--- Comment sent.')
                else:
                    self.to_log('--- Could not post comment. Moving on.')
            self.save_action(datum, author, parent_author, block_num, permlink, parent_permlink, self.RC_DAILY_LIMIT, 0, 0)
            return

        # Check the bot's wallet for sufficient funds
        if (not self.bot_has_funds()):
            self.to_log('OH NO! Ran out of money! Going to sleep until resupplied.')
            time.sleep(60)
            while (not self.bot_has_funds()):
                time.sleep(60)

            self.to_log('Got more tokens. Resuming work!')

        # Transfer the token
        if (self.config.enable_token_transfer):
            if tipping_level.tip_recipient > 0:
                recipient_memo_template = jinja2.Template(self.config.transfer_recipient_memo)
                self.hive_wallet.transfer(parent_author, tipping_level.tip_recipient, token_name, recipient_memo_template.render(sender_account=author, target_account=parent_author))
                self.to_log(f'--- sent {tipping_level.tip_recipient} {token_name} to {parent_author}')
            if tipping_level.tip_caller > 0:
                caller_memo_template = jinja2.Template(self.config.transfer_caller_memo)
                self.hive_wallet.transfer(author, tipping_level.tip_caller, token_name, caller_memo_template.render(sender_account=author, target_account=parent_author))
                self.to_log(f'--- sent {tipping_level.tip_caller} {token_name} to {author}')

            time.sleep(3)
            # IMPORTANT: save the fact in Database.
            # Otherwise if we crash during the rest of this block, the tip is sent again when we pick it up after restart!
            self.save_action(datum, author, parent_author, block_num, permlink, parent_permlink, self.RC_SUCCESS, tipping_level.tip_recipient, tipping_level.tip_caller)

            # Write the comment
            if (self.config.enable_comments):
                # Get the comment templates. 
                comment_success_template = jinja2.Template(open(file='comment_success.template', mode='r', encoding='utf-8').read())
                comment_body = comment_success_template.render(token_name=token_name, target_account=self.add_tagging_symbol(parent_author),
                                                               token_amount=tipping_level.tip_recipient,
                                                               token_amount_caller= tipping_level.tip_caller,
                                                               sender_account=self.add_tagging_symbol(author),
                                                               today_tips_count=calls_today+1,
                                                               max_daily_tips=tipping_level.calls)
                if self.config.enable_collection_post:
                    self.post_collection_comment(datum, comment_body)
                    self.to_log('--- Comment appended to daily collection.')
                elif (self.post_comment(f'@{author}/{permlink}', comment_body)):
                    self.to_log('--- Comment sent.')
                else:
                    self.to_log('--- Could not post comment. Moving on.')

            # Upvote the parent
            if self.has_voted(f'@{parent_author}/{parent_permlink}'):
                self.to_log('--- Vote already cast. Moving on.')
            elif (self.config.enable_upvote):
                self.hive_account.refresh()
                current_mana = self.hive_account.get_voting_power()
                if self.config.require_stake:
                    recipient_token_count = HiveBotUtils.get_staked_balance(parent_author, token_name)
                else:
                    recipient_token_count = HiveBotUtils.get_liquid_balance(parent_author, token_name)
                weight = int(max(min(self.config.upvote_weight, recipient_token_count), self.config.upvote_minweight))
                self.to_log(f'--- {parent_author} has {recipient_token_count:.2f} {self.config.token_name} in wallet. Vote weight set to {weight}')
                if (self.config.upvote_balance_linear):
                    if (current_mana<self.config.upvote_baseline):
                        weight = int(weight*(current_mana/self.config.upvote_baseline))
                        self.to_log(f"--- Mana at {current_mana:.2f} balancing vote to {weight}")
                    else:
                        self.to_log(f"--- Mana at {current_mana:.2f} no balancing needed. Vote at {weight}")
                else:
                    self.to_log(f"--- Mana at {current_mana:.2f} with fixed vote at {weight}")
                self.upvote(f'@{parent_author}/{parent_permlink}', weight)
            return
        
        ## If we reach this point no action was taken, because transfers are disabled. Record the fact in the database.
        self.save_action(datum, author, parent_author, block_num, permlink, parent_permlink, self.RC_TRANSFER_DISABLED, 0, 0)



    def run(self):
        """ Starts the main loop of the bot."""

        self.to_log(f'Bot is alive and looking for {self.config.tip_commands}')

        blockchain = Blockchain()

        # What was the last block we processed?
        # Will return none if this is the first time running, then we start listening to the current latest block
        start_block = self.config.current_block

        # Tell the world our starting block. This also means we're ready to process the blockchain at this point
        # If the config is set to 0 or negative value we want to go with live feed.
        if (start_block <=0):
            self.to_log('Going with live feed')
            start_block = None
        else:
            self.to_log(f'Picking up at block #{start_block}')

        # Actual main loop of the bot.
        # We run with three threads for catching up from older block numbers if we start again
        # after a pause. Seems to be the sweetspot for stability and performance.
        for operation in blockchain.stream(start=start_block, threading=True, thread_num=3):

            # Did we reach a new block number?
            # Memorize it as new starting block and write it down.
            if (operation['block_num'] != start_block):
                start_block = operation['block_num']
                self.config.current_block=start_block
                print(f'Reading Block #{start_block}')

            # We are only interested in comment operations.
            if (operation['type']=='comment'):
                self.process_comment_operation(operation)



