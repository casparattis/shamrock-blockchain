from typing import Any, Dict, List, Optional

import aiohttp

from shamrock.cmds.units import units
from shamrock.consensus.block_record import BlockRecord
from shamrock.rpc.farmer_rpc_client import FarmerRpcClient
from shamrock.rpc.full_node_rpc_client import FullNodeRpcClient
from shamrock.rpc.wallet_rpc_client import WalletRpcClient
from shamrock.util.config import load_config
from shamrock.util.default_root import DEFAULT_ROOT_PATH
from shamrock.util.ints import uint16
from shamrock.util.misc import format_bytes
from shamrock.util.misc import format_minutes

SECONDS_PER_BLOCK = (24 * 3600) / 43200


async def get_plots(farmer_rpc_port: int) -> Optional[Dict[str, Any]]:
    try:
        config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
        self_hostname = config["self_hostname"]
        if farmer_rpc_port is None:
            farmer_rpc_port = config["farmer"]["rpc_port"]
        farmer_client = await FarmerRpcClient.create(self_hostname, uint16(farmer_rpc_port), DEFAULT_ROOT_PATH, config)
        plots = await farmer_client.get_plots()
    except Exception as e:
        if isinstance(e, aiohttp.ClientConnectorError):
            print(f"Connection error. Check if farmer is running at {farmer_rpc_port}")
        else:
            print(f"Exception from 'harvester' {e}")
        return None
    farmer_client.close()
    await farmer_client.await_closed()
    return plots


async def get_blockchain_state(rpc_port: int) -> Optional[Dict[str, Any]]:
    blockchain_state = None
    try:
        config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
        self_hostname = config["self_hostname"]
        if rpc_port is None:
            rpc_port = config["full_node"]["rpc_port"]
        client = await FullNodeRpcClient.create(self_hostname, uint16(rpc_port), DEFAULT_ROOT_PATH, config)
        blockchain_state = await client.get_blockchain_state()
    except Exception as e:
        if isinstance(e, aiohttp.ClientConnectorError):
            print(f"Connection error. Check if full node is running at {rpc_port}")
        else:
            print(f"Exception from 'full node' {e}")

    client.close()
    await client.await_closed()
    return blockchain_state


async def get_average_block_time(rpc_port: int) -> float:
    try:
        blocks_to_compare = 500
        config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
        self_hostname = config["self_hostname"]
        if rpc_port is None:
            rpc_port = config["full_node"]["rpc_port"]
        client = await FullNodeRpcClient.create(self_hostname, uint16(rpc_port), DEFAULT_ROOT_PATH, config)
        blockchain_state = await client.get_blockchain_state()
        curr: Optional[BlockRecord] = blockchain_state["peak"]
        if curr is None or curr.height < (blocks_to_compare + 100):
            client.close()
            await client.await_closed()
            return SECONDS_PER_BLOCK
        while curr is not None and curr.height > 0 and not curr.is_transaction_block:
            curr = await client.get_block_record(curr.prev_hash)
        if curr is None:
            client.close()
            await client.await_closed()
            return SECONDS_PER_BLOCK

        past_curr = await client.get_block_record_by_height(curr.height - blocks_to_compare)
        while past_curr is not None and past_curr.height > 0 and not past_curr.is_transaction_block:
            past_curr = await client.get_block_record(past_curr.prev_hash)
        if past_curr is None:
            client.close()
            await client.await_closed()
            return SECONDS_PER_BLOCK

        client.close()
        await client.await_closed()
        return (curr.timestamp - past_curr.timestamp) / (curr.height - past_curr.height)

    except Exception as e:
        if isinstance(e, aiohttp.ClientConnectorError):
            print(f"Connection error. Check if full node is running at {rpc_port}")
        else:
            print(f"Exception from 'full node' {e}")

    client.close()
    await client.await_closed()
    return SECONDS_PER_BLOCK


async def get_wallets_stats(wallet_rpc_port: int) -> Optional[Dict[str, Any]]:
    amounts = None
    try:
        config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
        self_hostname = config["self_hostname"]
        if wallet_rpc_port is None:
            wallet_rpc_port = config["wallet"]["rpc_port"]
        wallet_client = await WalletRpcClient.create(self_hostname, uint16(wallet_rpc_port), DEFAULT_ROOT_PATH, config)
        amounts = await wallet_client.get_farmed_amount()
    #
    # Don't catch any exceptions, the caller will handle it
    #
    finally:
        wallet_client.close()
        await wallet_client.await_closed()

    return amounts


async def is_farmer_running(farmer_rpc_port: int) -> bool:
    is_running = False
    try:
        config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
        self_hostname = config["self_hostname"]
        if farmer_rpc_port is None:
            farmer_rpc_port = config["farmer"]["rpc_port"]
        farmer_client = await FarmerRpcClient.create(self_hostname, uint16(farmer_rpc_port), DEFAULT_ROOT_PATH, config)
        await farmer_client.get_connections()
        is_running = True
    except Exception as e:
        if isinstance(e, aiohttp.ClientConnectorError):
            print(f"Connection error. Check if farmer is running at {farmer_rpc_port}")
        else:
            print(f"Exception from 'farmer' {e}")

    farmer_client.close()
    await farmer_client.await_closed()
    return is_running


async def get_challenges(farmer_rpc_port: int) -> Optional[List[Dict[str, Any]]]:
    signage_points = None
    try:
        config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
        self_hostname = config["self_hostname"]
        if farmer_rpc_port is None:
            farmer_rpc_port = config["farmer"]["rpc_port"]
        farmer_client = await FarmerRpcClient.create(self_hostname, uint16(farmer_rpc_port), DEFAULT_ROOT_PATH, config)
        signage_points = await farmer_client.get_signage_points()
    except Exception as e:
        if isinstance(e, aiohttp.ClientConnectorError):
            print(f"Connection error. Check if farmer is running at {farmer_rpc_port}")
        else:
            print(f"Exception from 'farmer' {e}")

    farmer_client.close()
    await farmer_client.await_closed()
    return signage_points


async def challenges(farmer_rpc_port: int, limit: int) -> None:
    signage_points = await get_challenges(farmer_rpc_port)
    if signage_points is None:
        return None

    signage_points.reverse()
    if limit != 0:
        signage_points = signage_points[:limit]

    for signage_point in signage_points:
        print(
            (
                f"Hash: {signage_point['signage_point']['challenge_hash']} "
                f"Index: {signage_point['signage_point']['signage_point_index']}"
            )
        )


async def summary(rpc_port: int, wallet_rpc_port: int, harvester_rpc_port: int, farmer_rpc_port: int) -> None:
    all_plots = await get_plots(farmer_rpc_port)
    blockchain_state = await get_blockchain_state(rpc_port)
    farmer_running = await is_farmer_running(farmer_rpc_port)

    wallet_not_ready: bool = False
    wallet_not_running: bool = False
    amounts = None
    try:
        amounts = await get_wallets_stats(wallet_rpc_port)
    except Exception as e:
        if isinstance(e, aiohttp.ClientConnectorError):
            wallet_not_running = True
        else:
            wallet_not_ready = True

    print("Farming status: ", end="")
    if blockchain_state is None:
        print("Not available")
    elif blockchain_state["sync"]["sync_mode"]:
        print("Syncing")
    elif not blockchain_state["sync"]["synced"]:
        print("Not synced or not connected to peers")
    elif not farmer_running:
        print("Not running")
    else:
        print("Farming")

    if amounts is not None:
        print(f"Total shamrock farmed: {amounts['farmed_amount'] / units['shamrock']}")
        print(f"User transaction fees: {amounts['fee_amount'] / units['shamrock']}")
        print(f"Block rewards: {(amounts['farmer_reward_amount'] + amounts['pool_reward_amount']) / units['shamrock']}")
        print(f"Last height farmed: {amounts['last_height_farmed']}")

    total_plot_size = 0
    total_plots = 0
    if all_plots is not None:
        for harvester_ip, plots in all_plots.items():
            if harvester_ip == "success":
                # This key is just "success": True
                continue
            total_plot_size_harvester = sum(map(lambda x: x["file_size"], plots["plots"]))
            total_plot_size += total_plot_size_harvester
            total_plots += len(plots["plots"])
            print(f"Harvester {harvester_ip}:")
            print(f"   {len(plots['plots'])} plots of size: {format_bytes(total_plot_size_harvester)}")

        print(f"Plot count for all harvesters: {total_plots}")

        print("Total size of plots: ", end="")
        print(format_bytes(total_plot_size))
    else:
        print("Plot count: Unknown")
        print("Total size of plots: Unknown")

    if blockchain_state is not None:
        print("Estimated network space: ", end="")
        print(format_bytes(blockchain_state["space"]))
    else:
        print("Estimated network space: Unknown")

    minutes = -1
    if blockchain_state is not None and all_plots is not None:
        proportion = total_plot_size / blockchain_state["space"] if blockchain_state["space"] else -1
        minutes = int((await get_average_block_time(rpc_port) / 60) / proportion) if proportion else -1

    if all_plots is not None and total_plots == 0:
        print("Expected time to win: Never (no plots)")
    else:
        print("Expected time to win: " + format_minutes(minutes))

    if amounts is None:
        if wallet_not_running:
            print("For details on farmed rewards and fees you should run 'shamrock start wallet' and 'shamrock wallet show'")
        elif wallet_not_ready:
            print("For details on farmed rewards and fees you should run 'shamrock wallet show'")
    else:
        print("Note: log into your key using 'shamrock wallet show' to see rewards for each key")
