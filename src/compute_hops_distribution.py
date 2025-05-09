# Function to Compute Hop Distribution in Parallel with Error Handling
import os
import time
import gzip
import pickle
import json
import multiprocessing as mp
from multiprocessing import cpu_count
import networkx as nx
import pandas as pd
from functools import partial
import traceback
from tqdm import tqdm

DATA_DIR = os.path.realpath(os.path.join(os.getcwd(), "..", "data"))
GRAPH_DIR = os.path.join(DATA_DIR, "graphs")
percentiles = [.01, .05, .1, .2, .25, .50, .75, .8, .9, .95, .99]


# Function to compute hop distribution for a single node
def compute_hop_for_node(graph, target_set, node):
    try:
        paths = nx.single_source_shortest_path_length(graph, node)
        return [hops for target, hops in paths.items() if target in target_set]
    except Exception as e:
        print(f"Error computing hop for node {node}: {e}")
        return []


# Parallel function to compute hop distribution with error handling
def compute_hop_distribution_parallel(graph, exchange_addresses, claim_receivers):
    num_workers = cpu_count() - 1
    target_set = {
        target for target in exchange_addresses if graph.has_node(target)}
    source_set = {
        claimer for claimer in claim_receivers if graph.has_node(claimer)}

    func = partial(compute_hop_for_node, graph, target_set)

    with mp.Pool(num_workers) as pool:
        try:
            results = pool.map(func, list(source_set))
        except Exception as e:
            print(f"Error during parallel processing: {e}")
            traceback.print_exc()
            return pd.Series([])

    hop_counts = [hop for sublist in results for hop in sublist]
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
    addresses = {"exchange_addresses": set(), "claim_receivers": set()}
    file_path = os.path.join(DATA_DIR, "exchanges_addresses.json")
    with open(file_path) as f:
        addresses["exchange_addresses"] = set(json.load(f))
    file_path = os.path.join(DATA_DIR, "claim_receivers_addresses.json")
    with open(file_path) as f:
        addresses["claim_receivers"] = json.load(f)
    return addresses


# Function to Compute Hop Distribution
def compute_hop_distribution(graph, exchange_addresses, claim_receivers):
    hop_counts = []
    target_set = {
        target for target in exchange_addresses if graph.has_node(target)}
    source_set = {
        claimer for claimer in claim_receivers if graph.has_node(claimer)}

    for node in source_set:
        paths = nx.single_source_shortest_path_length(graph, node)
        hop_counts.extend(
            [hops for target, hops in paths.items() if target in target_set])

    return pd.Series(hop_counts)


def check_for_hops(graph, exchange_addresses, claim_receivers):
    # Compute hop distribution for airdrop addresses
    hop_distribution = dict()
    print(len(claim_receivers), len(exchange_addresses))

    hop_distribution = compute_hop_distribution_parallel(
        graph, exchange_addresses=exchange_addresses, claim_receivers=claim_receivers)

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

        # print("Hop distribution:")
        # print(hop_distribution.describe(percentiles=percentiles).T)
        persist_hop_distribution(hop_distribution.to_list(), protocol)
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Execution time for {protocol}: {elapsed_time:.4f} seconds")


# Main function to demonstrate usage
def main():
    protocols = ["tornado", "ens", "dydx", "1inch", "gemstone",
                 "arkham", "lido", "arbitrum", "optimism", "uniswap"]
    process_protocols(protocols[:1])


if __name__ == "__main__":
    main()
