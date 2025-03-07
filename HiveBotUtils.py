from hiveengine.wallet import Wallet

###
### All the functions we need to gather information about a user's Hive Engine Token Balances
###

def get_liquid_balance(user: str, token: str) -> float:
    """ Return liquid (i.e. transferable) balance of token in user's wallet"""
    wallet_token_info = Wallet(user.lower()).get_token(token)
    if not wallet_token_info:
        return 0
    else:
        return float(wallet_token_info['balance'])

def get_staked_balance(user: str, token: str) -> float:
    """ Return staked balance of token in user's wallet"""
    wallet_token_info = Wallet(user.lower()).get_token(token)
    if not wallet_token_info:
        return 0
    else:
        return float(wallet_token_info['stake'])

def get_total_balance(user: str, token: str) -> float:
    """ Returns sum of liquid and staked balance of token in user's wallet"""
    wallet_token_info = Wallet(user.lower()).get_token(token)
    if not wallet_token_info:
        return 0
    else:
        return float(wallet_token_info['balance'])+float(wallet_token_info['stake'])

def get_balances(user: str, token: str) -> dict:
    """ Returns all three (liquid, stake, total) values for token in user's wallet
    
        :param str user: Whose wallet to check
        :param str token: Name of token to get the balances for

        :returns dict {'liquid', 'stake', 'total'}: The balances of token in user's wallet    
    """
    wallet_token_info = Wallet(user.lower()).get_token(token)
    if not wallet_token_info:
        return {'liquid': 0,
                'stake': 0,
                'total': 0
                }
    else:
        return {'liquid': float(wallet_token_info['balance']),
                'stake': float(wallet_token_info['stake']),
                'total': float(wallet_token_info['balance'])+float(wallet_token_info['stake'])
                }



