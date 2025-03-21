# Johnnatan Messias
# Data collection
# This code is available on the following two GitHub repositories:

# https://github.com/johnnatan-messias/ethereum-crawler/blob/main/1-dataset.ipynb
# https://github.com/johnnatan-messias/chainlink-data-feed-crawler

import itertools
import json
import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

import requests
from tqdm.notebook import tqdm
from web3 import Web3


def get_abi_from_etherscan(contract_address, etherscan_api_key=os.environ["ETHERSCAN_API_KEY"], n_err=5):
    # Get contract ABI from Etherscan
    api_url_format = 'https://api.etherscan.io/api?module=contract&action=getabi&address={address}&apikey={apikey}'
    api_url = api_url_format.format(
        address=contract_address, apikey=etherscan_api_key)
    abi = dict()
    while n_err > 0:
        try:
            rq = requests.get(api_url)
            if rq.status_code == 200:
                response = rq.json()['result']
                abi = json.loads(response)
                rq.connection.close()
                break
        except TimeoutError:
            n_err -= 1
            time.sleep(.5)
        finally:
            rq.connection.close()

    if n_err == 0:
        raise (TimeoutError('Error: Cannot get ABI'))
    return abi


def get_contract(w3, contract_address, abi_contract_address=None):
    # Get contract ABI from Etherscan
    if abi_contract_address is None:
        abi_contract_address = contract_address
    abi = get_abi_from_etherscan(abi_contract_address)
    # Create contract object
    contract = w3.eth.contract(address=contract_address, abi=abi)
    return contract


def get_events_from_contract(params):
    # Get all event data from a contract
    contract_event_function = params['contract_event_function']
    start_block = params['start_block']
    end_block = params['end_block']

    filtered_event = list()
    n_err = 15
    while n_err > 0:
        # filtered_events_function = contract_event_function.get_logs(
        #     from_block=start_block, to_lock=end_block)
        try:
            filtered_event = contract_event_function.get_logs(
                from_block=start_block, to_block=end_block)
            break
        except TimeoutError:
            n_err -= 1
            time.sleep(.5)
    if n_err == 0:
        raise (TimeoutError('Error: Cannot get events from contract!'))
    return filtered_event


def get_batch_intervals(block_start, block_end, batch_size):
    # Improved version of the line code below
    # pd.interval_range(start=block_number_min, end=block_number_max, freq=batch_size)
    intervals = list()
    block_numbers = list(range(block_start, block_end, batch_size))
    for block_number in block_numbers:
        block_interval_start = block_number
        block_interval_end = min(block_number + batch_size - 1, block_end)
        intervals.append((block_interval_start, block_interval_end))
    return intervals


def get_events(contract_event_function, start_block, end_block, batch_size=5000, max_workers=20):
    # Get all event data from a contract in batches
    # This is a multithreading code and run faster than the previous version
    event_list = list()
    dict_keys = ['contract_event_function', 'start_block', 'end_block']
    intervals = get_batch_intervals(
        block_start=start_block, block_end=end_block, batch_size=batch_size)
    intervals = list(dict(zip(dict_keys, (contract_event_function, *interval)))
                     for interval in intervals)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        print(contract_event_function.event_name)
        event_list = list(
            tqdm(pool.map(get_events_from_contract, intervals), total=len(intervals), desc=contract_event_function.event_name))
    event_list = list(itertools.chain(*event_list))
    return event_list


def get_all_events_from_contract(contract, start_block, end_block, batch_size=5000, max_workers=20, events=None):
    # Get all events data from a contract
    contract_events = dict()
    if not events:
        events = contract.events
    for event in events:
        contract_events[event.event_name] = get_events(contract_event_function=contract.events[event.event_name],
                                                       start_block=start_block, end_block=end_block,
                                                       batch_size=batch_size, max_workers=max_workers)
    return contract_events


def get_block(params):
    return params['lib'].eth.get_block(params['block_number'])


def get_blocks(w3, block_numbers, max_workers=20):
    blocks = []
    print('Prepearing to gather blocks...')
    params = [{'lib': w3, 'block_number': block_number}
              for block_number in block_numbers]
    print('Starting...')
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        blocks = list(tqdm(pool.map(get_block, params),
                      total=len(block_numbers), desc='Gathering blocks...'))
    return blocks


def to_checksum_address(address):
    return Web3.to_checksum_address(address.lower())


def get_logs_from_contract(address, fromBlock, toBlock, batch_size=500):
    logs = []
    intervals = get_batch_intervals(fromBlock, toBlock, batch_size=batch_size)
    try:
        for block_start, block_end in tqdm(intervals, desc='Getting logs', ascii=True):
            batch = w3.eth.get_logs(filter_params={
                'address': address, 'fromBlock': block_start, 'toBlock': block_end})
            if batch:
                logs += batch
    except Exception as e:
        print(traceback.format_exc())
        print(block_start, block_end, e)
    return logs


def get_transaction(params):
    tx_data = {}
    tx_data['tx'] = params['lib'].eth.get_transaction(
        transaction_hash=params['tx_hash'])
    tx_data['receipt'] = params['lib'].eth.get_transaction_receipt(
        transaction_hash=params['tx_hash'])
    return tx_data


def get_transactions(w3, txs_hashes, max_workers=20):
    txs = []
    params = [{'lib': w3, 'tx_hash': tx_hash}
              for tx_hash in txs_hashes]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        txs = list(tqdm(pool.map(get_transaction, params),
                        total=len(txs_hashes), desc='Gathering transactions...'))
    return txs
