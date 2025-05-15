# Function to Compute Hop Distribution in Parallel with Error Handling
import os
import time
import gzip
import pickle
import json
import networkx as nx
import pandas as pd
import traceback
from tqdm import tqdm

DATA_DIR = os.path.realpath(os.path.join(os.getcwd(), "..", "data"))
GRAPH_DIR = os.path.join(DATA_DIR, "graphs")
percentiles = [.01, .05, .1, .2, .25, .50, .75, .8, .9, .95, .99]


# Function to compute hop distribution for a single node
def compute_hop_for_node(graph, source_set, target_set):
    paths = nx.multi_source_dijkstra_path_length(
        G=graph, sources=source_set)
    hop_distances = [hops for target,
                     hops in paths.items() if target in target_set]

    return hop_distances


# Parallel function to compute hop distribution with error handling
def compute_hop_distribution_parallel(graph, exchange_addresses, claim_receivers):
    # Source will be the exchanges
    source_set = frozenset(
        address for address in exchange_addresses if graph.has_node(address))
    # Target will be the accounts
    target_set = frozenset(
        address for address in claim_receivers if graph.has_node(address))

    # Reversing graph to check convert from Address -> Exchange to Exchange -> Address
    graph_reversed = graph.reverse()

    hop_counts = compute_hop_for_node(
        graph=graph_reversed, source_set=source_set, target_set=target_set)

    hop_counts = [hop for hop in hop_counts if hop > 0]
    return pd.Series(hop_counts)


# Main function to demonstrate usage
def load_graph_from_gzip(protocol):
    file_path = os.path.join(
        GRAPH_DIR, "full_graph_{}.gpickle".format(protocol))
    try:
        with gzip.open(file_path, 'rb') as f:
            graph = pickle.load(f)
        print(f"Graph successfully loaded from {file_path}")
        print("The graph contains {} nodes and {} edges.".format(
            graph.number_of_nodes(), graph.number_of_edges()))
        return graph
    except Exception as e:
        print(f"Error loading graph from {file_path}: {e}")
        traceback.print_exc()
        return None


def load_addresses():
    addresses = {"exchange_addresses": set(), "claim_receivers": {}}

    try:
        with open(os.path.join(DATA_DIR, "exchanges_addresses.json")) as f:
            addresses["exchange_addresses"] = set(json.load(f))

        with open(os.path.join(DATA_DIR, "claim_receivers_addresses.json")) as f:
            addresses["claim_receivers"] = json.load(f)
    except Exception as e:
        print(f"Error loading addresses: {e}")
        traceback.print_exc()

    return addresses


def check_for_hops(graph, exchange_addresses, claim_receivers):
    # Compute hop distribution for airdrop addresses
    hop_distribution = compute_hop_distribution_parallel(
        graph, exchange_addresses, claim_receivers)
    return hop_distribution


def persist_hop_distribution(data, protocol):
    file_path = os.path.join(
        DATA_DIR, "hop_distribution_{}.json".format(protocol))
    with open(file_path, "w") as f:
        json.dump(data, f)


def process_protocols(protocols):
    # Define target addresses and claim receivers
    addresses = load_addresses()
    exchange_addresses = addresses["exchange_addresses"]
    claim_receivers = addresses["claim_receivers"]

    for protocol in tqdm(protocols, "Processing protocols"):
        start_time = time.time()
        print(">>>>", protocol.upper())
        # Load graph from file
        graph = load_graph_from_gzip(protocol=protocol)

        # Compute hop distribution in parallel
        hop_distribution = check_for_hops(
            graph, exchange_addresses, claim_receivers[protocol])

        persist_hop_distribution(hop_distribution.to_list(), protocol)
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Execution time for {protocol}: {elapsed_time:.4f} seconds")


# Main function to demonstrate usage
def main():
    protocols = ["tornado", "gemstone", "ens", "dydx", "1inch",
                 "arkham", "lido", "uniswap", "optimism", "arbitrum"]
    process_protocols(protocols)


if __name__ == "__main__":
    main()
