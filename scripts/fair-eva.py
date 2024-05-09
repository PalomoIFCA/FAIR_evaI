#!/usr/bin/env python3

"""
# Full example
python3 scripts/fair-eva.py --id 1b67c7f4-3cb8-473e-91a9-0191a1fa54a8 --plugin epos --repository https://www.ics-c.epos-eu.org/api/v1

# EXAMPLES
# EPOS Production API
id = "12b76f8e-d10e-4c5d-a113-4855f6bc3435"
oaibase = "https://www.ics-c.epos-eu.org/api/v1"
repo = "epos"

# EPOS prototype API
oaibase =  'https://ics-c.epos-ip.org/development/k8s-epos-deploy/dt-geo/api/v1'
ide = '46676a31-fa8e-4a4a-a3c0-15d689783a08'

# DIGITAL CSIC
id = "http://hdl.handle.net/10261/157765"
oaibase = "http://digital.csic.es/dspace-oai/request"
repo = "oai-pmh"
"""

import argparse
import json
import logging
import requests
import socket
import sys
import time
from flask_babel import Babel, gettext, lazy_gettext as _l
from prettytable import PrettyTable


def get_input_args():
    parser = argparse.ArgumentParser(
        description=("Command-line interface for FAIR EVA tool")
    )
    parser.add_argument(
        "-i",
        "--id",
        metavar="IDENTIFIER",
        type=str,
        help="Identifier of the (meta)data",
    )
    parser.add_argument(
        "-p", "--plugin", metavar="PLUGIN", type=str, help="FAIR EVA plugin name"
    )
    parser.add_argument(
        "-r",
        "--repository",
        metavar="URL",
        type=str,
        help="(meta)data repository endpoint",
    )
    parser.add_argument(
        "--api-endpoint",
        metavar="URL",
        type=str,
        default="http://localhost:9090/v1.0/rda/rda_all",
        help=(
            "Endpoint to perform HTTP request. Example: "
            "http://localhost:9090/v1.0/rda/rda_all"
        ),
    )
    parser.add_argument("-j", "--json", action="store_true")
    parser.add_argument("--totals", action="store_true")

    parser.add_argument(
        "-s", "--search", metavar="search", type=str, help="data asset to look for"
    )

    return parser.parse_args()


def is_port_open():
    is_port_open = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("127.0.0.1", 9090))
    if result == 0:
        is_port_open = True
    sock.close()

    return is_port_open


def calcpoints(result, print_scores=False, print_fullscores=False):
    keys = ["findable", "accessible", "interoperable", "reusable", "total"]
    values = [0, 0, 0, 0, 0]
    result_points = 0
    weight_of_tests = 0
    points = dict(zip(keys, values))

    for key in keys[:-1]:
        g_weight = 0
        g_points = 0
        for kk in result[key]:
            result[key][kk]["indicator"] = gettext(
                "%s.indicator" % result[key][kk]["name"]
            )

            if print_fullscores == True:
                print(
                    "In "
                    + str(kk)
                    + " your item has "
                    + str(result[key][kk]["points"])
                    + " points"
                )
            result[key][kk]["name_smart"] = gettext("%s" % result[key][kk]["name"])

            weight = result[key][kk]["score"]["weight"]
            weight_of_tests += weight
            g_weight += weight
            result_points += result[key][kk]["points"] * weight
            g_points += result[key][kk]["points"] * weight

        points[key] = round((g_points / g_weight), 3)
    points["total"] = round((result_points / weight_of_tests), 2)

    return points


def format_msg_for_table(message_data):
    output_message = "Not available"
    # FIXME Check to overcome issue: https://github.com/EOSC-synergy/FAIR_eva/issues/188
    if isinstance(message_data, str):
        output_message = message_data
    else:
        if len(message_data) > 0:
            # FIXME Overcome same issue as above: https://github.com/EOSC-synergy/FAIR_eva/issues/188
            if isinstance(message_data[0], str):
                output_message = "\n".join(message_data)
            else:
                if len(message_data) > 1:
                    output_message = "\n".join(
                        [
                            "%s (points: %s)" % (item["message"], item["points"])
                            for item in message_data
                        ]
                    )
                elif len(message_data) == 1:
                    output_message = message_data[0].get("message", "Not available")
    return output_message


def print_table(result_json, show_totals=False):
    for identifier, fair_results in result_json.items():
        table = PrettyTable()
        table.field_names = ["FAIR indicator", "Score", "Output"]
        table.align = "l"
        table._max_width = {"Output": 100}

        # Split by principle: required for setting dividers in the resultant table
        indicators_by_principle = {}
        for principle, principle_result in fair_results.items():
            indicators_by_principle[principle] = list(principle_result.values())

        for principle, indicator_list in indicators_by_principle.items():
            indicator_total = len(indicator_list)
            indicator_count = 0
            for indicator_result in indicator_list:
                # Format output message
                output_message = format_msg_for_table(indicator_result.get("msg", []))
                # Set divider
                has_divider = False
                indicator_count += 1
                if indicator_count == indicator_total:
                    has_divider = True
                # Truncate points to two decimals
                points = indicator_result["points"]
                if isinstance(points, float):
                    points = "%.2f" % points
                table.add_row(
                    [
                        indicator_result["name"].upper(),
                        points,
                        output_message,
                    ],
                    divider=has_divider,
                )

        # Implementation of show_totals
        if show_totals:
            # per principle
            table_summary = PrettyTable()
            table_summary.field_names = ["FAIR principle", "Score"]
            table_summary.align = "l"
            summary_scores = calcpoints(fair_results)
            total_score = summary_scores.pop("total", "NA")
            principle_len = len(summary_scores)
            principle_count = 0
            has_divider = False
            for principle_name, principle_score in summary_scores.items():
                principle_count += 1
                if principle_count == principle_len:
                    has_divider = True
                if isinstance(principle_score, float):
                    principle_score = "%.2f" % principle_score
                table_summary.add_row(
                    [principle_name.capitalize(), principle_score], divider=has_divider
                )
            table_summary.add_row(["Total", total_score])
            print(table_summary)

        print(table)


def search(keytext):
    args = get_input_args()
    max_tries = 5

    headers = {
        "accept": "application/json",
    }
    good = 0
    params = {"facets": "false", "q": keytext}
    if args.plugin == "epos":
        response = requests.get(
            metadata_endpoint + "/resources/search",
            params=params,
            headers=headers,
        )
        terms = response.json()
        number_of_items = len(terms["results"]["distributions"])
        table = PrettyTable()
        table.field_names = [
            "Tittle",
            "Index",
        ]
        table.align = "l"
        table._max_width = {"Output": 100}
        for index in range((len(terms["results"]["distributions"]))):
            if (index + 1) % 5 == 0:
                div = True
            else:
                div = False
            table.add_row(
                [
                    terms["results"]["distributions"][index]["title"],
                    index,
                ],
                divider=div,
            )
        print(table)
        for j in range(max_tries):
            ind = input(
                "Please choose the index of the item you want to evaluate. From 0 to "
                + str(len(terms["results"]["distributions"]) - 1)
                + " "
            )
            try:
                if int(ind) > (-1) and int(ind) < number_of_items:
                    good = 1
            except:
                print(
                    "Please introduce an integer between 0 and " + str(number_of_items)
                )
            if good == 1:
                break
        if good == 0:
            print("Max tries , restart program")
            return ()
        return terms["results"]["distributions"][int(ind)]["id"]
    else:
        print("The search function is only availbale for the following plugins: epos")
        sys.exit()


def main():
    global metadata_endpoint
    logging.basicConfig(level=logging.INFO)

    args = get_input_args()
    url = args.api_endpoint
    if args.repository == None:
        response = requests.get(
            "http://localhost:9090/v1.0/endpoints?plugin=" + args.plugin
        )
        if response.status_code == 404:
            print(
                "Input plugin not found. Look for plugins in the plugins folder. The accepted plugins for this script are: "
                + str(response.json().keys())
            )
            return "Input plugin not found"
        else:
            metadata_endpoint = response.json()

    else:
        metadata_endpoint = args.repository

    is_api_running = False

    for i in range(1, 5):
        if is_port_open():
            logging.debug("FAIR-eva API running on port 9090")
            is_api_running = True
            break
        else:
            logging.debug("FAIR-eva API not running: port 9090 not open")
            logging.debug("Sleeping for 5 seconds..")
            time.sleep(5)
    if not is_api_running:
        logging.error("FAIR-eva API was not able to launch: exiting")
        sys.exit(-1)
    if args.search:
        identifier = search(args.search)
    else:
        identifier = args.id

    headers = {"Content-Type": "application/json"}
    data = {
        "id": identifier,
        "repo": args.plugin,
        "oai_base": metadata_endpoint,
        "lang": "EN",
    }

    r = requests.post(url, data=json.dumps(data), headers=headers)

    if args.json:
        print(r.json())
    else:
        show_totals = False
        if args.totals:
            show_totals = True
        print_table(r.json(), show_totals=show_totals)

        if args.search or not args.repository:
            print("For a faster execution you may use: ")
            command = (
                "python3 scripts/fair-eva.py --id "
                + identifier
                + " --plugin epos -r "
                + metadata_endpoint
            )
            if args.json:
                command += " -j "

            if args.totals:
                command += " --totals "
            print(command)


main()
