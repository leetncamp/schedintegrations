#!/usr/bin/env python

import os
import sys
import json

from pdb import set_trace as debug
import dateutil.parser
import datetime
import pytz
from pdb import set_trace as debug
from argparse import ArgumentParser
import copy
from email.utils import parseaddr

parser = ArgumentParser()
parser.add_argument("--clearAll", action="store_true", help="delete any existing webinars that start with AIWeb")
parser.add_argument("--users", action="store_true")
parser.add_argument("--meeting", action="store_true", help="create a meeting not a webinar")

ns = parser.parse_args()

from secrets import *
mytz = pytz.timezone("America/Los_Angeles")
UTC = pytz.timezone("UTC")
NOW = datetime.datetime.now()

integrations_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(integrations_dir, "zoomus"))
import copy

timeformat = "%Y-%m-%dT%H:%M:00Z"   # the python datetime object should be in UTC time.
roundingerror = datetime.timedelta(microseconds=5)


#if ns.clearAll:
#    webinars = json.loads(client.webinar.list(user_id=user_id, page_size=300).content).get("webinars")
#    while webinars:
#        print("Found {0}".format(len(webinars)))
#        for webinar in webinars:
#            name = webinar.get("topic")
#            if name in ["Zoom Meeting", "AIWeb", "ICLR Meeting", "Lee and Andrea"]:
#                result = client.webinar.delete(user_id=user_id, id=webinar.get("id"))
#            print(name)
#        webinars = json.loads(client.webinar.list(user_id=user_id, page_size=300).content).get("webinars")
#
#    meetings = json.loads(client.meeting.list(user_id=user_id, page_size=300).content).get("meetings")
#    while meetings:
#        print("Found {0}".format(len(meetings)))
#        for meeting in meetings:
#            name = meeting.get("topic")
#            if name in ["Zoom Meeting", "AIWeb", "ICLR Meeting", "Lee Campbell's Zoom Meeting"]:
#                result = client.meeting.delete(user_id=user_id, id=meeting.get("id"))
#            print(name)
#        meetings = json.loads(client.webinar.list(user_id=user_id, page_size=300).content).get("meetings")
#    sys.exit()
#
#if ns.users:
#    template = {
#        "action":"create",
#        "user_info": {
#            "type":1
#        }
#    }
#    #needed_users = [{"email":'brockmeyer@salk.edu', "first_name":"Brad", "last_name":"Brockmeyer"}, {"email":"terrence.gaines@hp.com", "first_name":"Terrence", "last_name":"Gaines"}, {"email":"meperry@salk.edu", "first_name":"Mary Ellen", "last_name":"Perry"}]
#    needed_users = [{"email":"terrence.gaines@hp.com", "first_name":"Terrence", "last_name":"Gaines"}]
#    existing_emails = [item.get("email") for item in user_list.get("users")]
#
#    for user in needed_users:
#        if not user.get("email") in existing_emails:
#            this_template = copy.copy(template)
#            this_template['user_info'].update(user)
#            result = client.user.create(**this_template)
#            print(result.content)
#    sys.exit()

webinar_update_errors = {
    200: "Webinar subscription plan is missing.",
    204: "Webinar Updated",
    300: "Invalid webinar Id or Invalid recurrence settings",
    400: "Bad Request.  Invalid User or access denied to the meeting. Are you the host?",
}

meeting_update_errors = {
    204: "Meeting Updated",
    300: "Invalid enforce_login_domains, separate multiple domains by semicolon, OR The maximum of meetings can be created/updated for a single user in one day.",
    400: "Bad Request. Invalid User. Are you the host?"
}


results = {}



existing_zoom_events = {}
existing_checked = False


def get_existing_meetings():

    global existing_zoom_events
    global existing_checked

    existing_meetings_result = client.meeting.list(user_id=user_id, page_size=300)
    if existing_meetings_result.ok:
        emresults = json.loads(existing_meetings_result.content)
        existing_meeting_list = emresults.get("meetings")
        existing_zoom_events = {item.get("agenda"): item for item in existing_meeting_list}
        print("Found {} existing meetings".format(len(existing_zoom_events)))
        print("Total reported: {}".format(emresults.get("total_records")))

    existing_webinars_result = client.webinar.list(user_id=user_id, page_size=300)
    if existing_webinars_result.ok:
        emresults = json.loads(existing_webinars_result.content)
        existing_webinar_list = emresults.get("webinars")
        print("Found {} existing webinars".format(len(existing_webinar_list)))
        print("Total reported: {}".format(emresults.get("total_records")))
        existing_webinars = {item.get("agenda"): item for item in existing_webinar_list}

    existing_zoom_events.update(existing_webinars) 
    existing_checked = True
    
    try:
        del existing_zoom_events[None]
    except KeyError:
        pass






def create_or_update_zoom(excel_data):

    """Handle starttime and endtime as strings or naive datetime objects depending on how the user typed them in"""

    global existing_zoom_events
    global existing_checked

    if not existing_checked:
        get_existing_meetings() #Leave a dictionary of existing zoom events in the global namespace

    starttime = excel_data.get("starttime")
    endtime = excel_data.get("endtime")
    
    if starttime and endtime:
        
        if type(starttime) == str:
            starttime = datetime.datetime.strptime(starttime, "%Y-%m-%dT%H:%M:00Z")
            endtime = datetime.datetime.strptime(endtime, "%Y-%m-%dT%H:%M:00Z")

    
        timezone_name = excel_data.get("timezone")
        if not timezone_name:
            timezone_name = "UTC"
        TZ = pytz.timezone(timezone_name)

        starttime += roundingerror  #Somemtimes we get a rounding error from Excel. Round to nearest.
        starttime = starttime.replace(microsecond=0)
        endtime += roundingerror  
        endtime = endtime.replace(microsecond=0)
        starttime = TZ.localize(starttime)
        endtime = TZ.localize(endtime)
        utc_starttime = UTC.normalize(starttime).strftime(timeformat)
        utc_endtime = UTC.normalize(endtime).strftime(timeformat)
        meeting_type = excel_data.get("meeting_or_webinar")


        """Update an existing meeting if there is one noted in the excel spreadsheet"""
        
        if meeting_type in ['meeting', "webinar"]:
            peerreviewid = excel_data.get("peerreviewid")
            existing_zoom_event = existing_zoom_events.get(peerreviewid)
            action = "update" if existing_zoom_event else "create"
            """"Create or update a new meeting or webinar"""
            zoom_data = copy.copy(eval("{0}_defaults".format(meeting_type)))

            """Load the defaults definition"""
            zoom_data = copy.copy(eval("{0}_defaults".format(meeting_type)))
            zoom_data.update({
                "agenda": str(peerreviewid),
                "topic": excel_data.get("title"),
                "start_time": utc_starttime,
                })
            zoom_data['recurrence'].update({"endtime": utc_endtime})
            if existing_zoom_event:
                function_call = eval("client.{0}.{1}".format(meeting_type, action))
                result = function_call(user_id=user_id, id=existing_zoom_event.get("id"), **zoom_data)
                if result.status_code != 204:
                    error_msg = eval("{0}_update_errors.get({1})".format(meeting_type, result.status_code))
                    print("An abnormal return code received when updating {0}. ".format(peerreviewid, error_msg))
            else:
                function_call = eval("client.{0}.{1}".format(meeting_type, action))
                result = function_call(user_id=user_id, **zoom_data)
            if result.content:
                return_val = json.loads(result.content)
            else:
                return_val = {}
            return_val['status'] = result.ok
            return_val['action'] = action

            if meeting_type == "webinar":
                pheaders = ['name', 'email']
                panelistStr = excel_data.get("panelists")
                panelist_list = [parseaddr(item) for item in panelistStr.split(",")]
                debug()
                plist = [dict(zip(pheaders, item)) for item in panelist_list]

                panelist_data = {
                    "panelists": plist
                }
                result = client.webinar.add_panelists(user_id=user_id, id=existing_zoom_event.get('id'), **panelist_data)
                if not result.ok:
                    print(json.loads(response.content))

            return(return_val)
        else:
            return({"action": "skipped due to incorrect meeting type in meeting_or_webinar: {}".format(excel_data.get("title"))})


    else:
        return({"action":"skipped"})
        return({"action": "skipped due to no start or no end time: {}".format(excel_data.get("title"))})



   