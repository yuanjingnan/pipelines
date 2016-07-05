#!/usr/bin/env python3
"""
Retrieves runcomplete records in MongoDB with user-specified parameters for filtering.
Unless specified by -w or --win, only the 7 most recent days of records are retrieved.
"""

#--- standard library imports
#
from argparse import ArgumentParser
from datetime import datetime, timedelta
import os
from pprint import PrettyPrinter
import subprocess
import sys
from time import mktime

#--- third-party imports
#
from flask import Flask, Markup, request, render_template
app = Flask(__name__)

#--- project specific imports
#
# add lib dir for this pipeline installation to PYTHONPATH
LIB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "lib"))
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)
from pipelines import generate_window
# FIXME: that function should go into lib
sys.path.insert(0, os.path.join(LIB_PATH, "..", "bcl2fastq"))
from mongo_status import mongodb_conn


__author__ = "Andreas Wilm"
__email__ = "wilma@gis.a-star.edu.sg"
__copyright__ = "2016 Genome Institute of Singapore"
__license__ = "The MIT License (MIT)"


def send_email(email, subject, message):
    """
    send_email("rpd@mailman.gis.a-star.edu.sg", "[RPD] " + os.path.basename(__file__), dictionary_checker())
    """
    subprocess.getoutput("echo '" + message + "' | mail -s '" + subject + "' " + email)


def dictionary_checker():
    send_email("rpd@mailman.gis.a-star.edu.sg", "[RPD] " + os.path.basename(__file__), "")


def instantiate_args():
    """
    Instantiates argparse object
    """
    instance = ArgumentParser(description=__doc__)
    instance.add_argument("-f", "--flask", action="store_true", help="use web server")
    instance.add_argument("-t", "--testing", action="store_true", help="use MongoDB test-server")
    instance.add_argument(
        "-s", "--status", help="filter records by analysis status (STARTED/FAILED/SUCCESS)")
    instance.add_argument("-m", "--mux", help="filter records by mux_id")
    instance.add_argument("-r", "--run", help="filter records by run")
    instance.add_argument("-w", "--win", type=int, help="filter records up to specified day(s) ago")

#    instance.add_argument("-a", "--arrange", help="arrange records by key and order")
    return instance.parse_args()


def instantiate_mongo(testing):
    """
    Instantiates MongoDB database object
    For Test Server, testing == true
    For Production Server, testing == false
    """
    return mongodb_conn(testing).gisds.runcomplete


def instantiate_query(args):
    """
    Instantiates MongoDB query dictionary object
    """
    instance = {}
    if args.status:
        instance["analysis.Status"] = args.status
    if args.mux:
        instance["analysis.per_mux_status.mux_id"] = args.mux
    if args.run:
        instance["run"] = {"$regex": "^" + args.run}
    if args.win:
        epoch_present, epoch_initial = generate_window(args.win)
    else:
        epoch_present, epoch_initial = generate_window(7)
    instance["timestamp"] = {"$gt": epoch_initial, "$lt": epoch_present}
    return instance


def merge_cells(parent_key, child_key, key):
    result = ""
    if child_key in key:
        if (str(key[child_key]) == "STARTED"):
            result += ("<span class='label label-pill label-warning'>" + str(key[child_key]) + "</span>")
        elif (str(key[child_key]) == "FAILED" or str(key[child_key]).upper() == "FALSE"):
            result += ("<span class='label label-pill label-danger'>" + str(key[child_key]).upper() + "</span>")
        elif (str(key[child_key]) == "SUCCESS" or str(key[child_key]).upper() == "TRUE"):
            result += ("<span class='label label-pill label-success'>" + str(key[child_key]).upper() + "</span>")
        elif (str(key[child_key]) == "TODO"):
            result += ("<span class='label label-pill label-default'>" + str(key[child_key]) + "</span>")
        else:
            result += str(key[child_key])
    return result


@app.route('/', methods=['POST'])
def form_post():
    """
    Flask callback function for POST requests from FORMS
    """
    list_from = request.form["from"].split("-")
    list_to = request.form["to"].split("-")
    if ("-".join(list_from) != "" or "-".join(list_to) != ""):
        if (len(list_from) == 3 and len(list_to) == 3):
            print("DATE FILTER: FROM " + "-".join(list_from) + " TO " + "-".join(list_to))
            epoch_initial = int(mktime(datetime(int(list_from[0]), int(list_from[1]), int(list_from[2])).timetuple()) * 1000)
            epoch_final = int(mktime((datetime(int(list_to[0]), int(list_to[1]), int(list_to[2])) + timedelta(days=1)).timetuple()) * 1000)
            instance = {}
            instance["timestamp"] = {"$gte": epoch_initial, "$lt": epoch_final}
#            instance["analysis"] = {"$exists": True}
            return form_none(instantiate_mongo(False).find(instance), "Showing RUN entries with TIMESTAMP from " + "-".join(list_from) + " to " + "-".join(list_to))

    return form_none(instantiate_mongo(False).find())


@app.route('/')
def form_none(mongo_results=instantiate_mongo(False).find(), date_filter=""):
    """
    Flask callback function for all requests
    """
    result = ""
    result += ("<div align='center'><a>" + date_filter + "</a></div>")
    for record in mongo_results:
        result += "<tr>"
        result += ("<td>" + str(record["run"]) + "</td>")

        if (len(str(record["timestamp"])) == 13):
            result += ("<td>" + str(datetime.fromtimestamp(record["timestamp"] / 1000).isoformat()).replace(":", "-") + "</td>")
        else:
            result += ("<td>" + str(record["timestamp"]) + "</td>")

        result += "<td>"
        if "analysis" in record:
            result += """
            <table class='table table-bordered table-hover table-fixed table-compact'>
                <thead>
                    <tr>
                        <th>ANALYSIS_ID</th>
                        <th>END_TIME</th>
                        <th>OUT_DIR</th>
                        <th>STATUS</th>
                        <th>MUX</th>
                    </tr>
                </thead>
                <tbody>
            """
            for analysis in record["analysis"]:
                result += "<tr>"
                result += ("<td>" + merge_cells("analysis", "analysis_id", analysis) + "</td>")
                result += ("<td>" + merge_cells("analysis", "end_time", analysis) + "</td>")
                result += ("<td>" + merge_cells("analysis", "out_dir", analysis) + "</td>")
                result += ("<td>" + merge_cells("analysis", "Status", analysis) + "</td>")
                result += "<td>"

                if "per_mux_status" in analysis:
                    result += """
                    <table class='table table-bordered table-hover table-fixed table-compact'>
                        <thead>
                            <tr>
                                <th>MUX_ID</th>
                                <th>ARCHIVE</th>
                                <th>DOWNSTREAM</th>
                                <th>STATS</th>
                                <th>STATUS</th>
                                <th>EMAIL</th>                            
                            </tr>
                        </thead>
                        <tbody>
                    """
                    for mux in analysis["per_mux_status"]:
                        result += "<tr>"
                        result += ("<td>" + merge_cells("per_mux_status", "mux_id", mux) + "</td>")
                        result += ("<td>" + merge_cells("per_mux_status", "ArchiveSubmission", mux) + "</td>")
                        result += ("<td>" + merge_cells("per_mux_status", "DownstreamSubmission", mux) + "</td>")
                        result += ("<td>" + merge_cells("per_mux_status", "StatsSubmission", mux) + "</td>")
                        result += ("<td>" + merge_cells("per_mux_status", "Status", mux) + "</td>")
                        result += ("<td>" + merge_cells("per_mux_status", "email_sent", mux) + "</td>")
                        result += "</tr>"
                    result += "</tbody></table>"
                else:
                    result += """
                    <table class='table table-bordered table-hover table-fixed table-compact invisible'>
                        <thead>
                            <tr>
                                <th>MUX_ID</th>
                                <th>ARCHIVE</th>
                                <th>DOWNSTREAM</th>
                                <th>STATS</th>
                                <th>STATUS</th>
                                <th>EMAIL</th>                            
                            </tr>
                        </thead>
                        <tbody>
                    """
                    result += "</tbody></table>"

                result += "</td>"
            result += "</tbody></table>"
        
        result += "</td>"
        result += "</tr>"
        result += "</tr>"
    return render_template("index.html", result=Markup(result))


def main():
    """
    Main function
    export FLASK_APP=bcl2fastq_records.py
    flask run --host=0.0.0.0
    """
    args = instantiate_args()
    mongo = instantiate_mongo(args.testing)
    query = instantiate_query(args)

    if args.flask:
        os.environ["FLASK_APP"] = os.path.basename(__file__)
        os.system("flask run --host=0.0.0.0")
        app.run()
    else:
        for record in mongo.find(query).sort([("timestamp", 1)]):
            result = record
            if (len(str(record["timestamp"])) == 13):
                result["timestamp"] = str(datetime.fromtimestamp(record["timestamp"] / 1000).isoformat()).replace(":", "-")
            else:
                result["timestamp"] = str(record["timestamp"])
            PrettyPrinter(indent=2).pprint(result)

if __name__ == "__main__":
#    app.run(debug=True)
    main()
