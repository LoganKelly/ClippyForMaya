#!/usr/bin/python

import os
import sys
import glob
import math
import datetime

import clippy_api as api


def get_all_clipped():
    clipped_by_dept = dict()
    for path in glob.glob(api.CLIPPED_PATH % '*'):
        username = os.path.basename(path).partition('.')[0]
        user = api.USERS_BY_NAME.get(username)
        if not user:
            continue
        clipped_by_dept.setdefault(user['department_token'], list()).append(user['real_name'])
    return clipped_by_dept
        

def main():
    show_active = '-a' in sys.argv
    show_clipped = '-c' in sys.argv
    now = datetime.datetime.now()
    secs_per_hour = 60.0 * 60.0
    users_by_dept = dict()
    for path in glob.glob(api.ACTIVE_USERS_PATH % '*'):
        username = os.path.basename(path).partition('.')[0]
        user = api.USERS_BY_NAME.get(username)
        if not user:
            continue
        modify_time = datetime.datetime.fromtimestamp(api.time_last_modified(path))
        age = (now - modify_time).total_seconds()
        hours = int(math.ceil(float(age) / secs_per_hour))
        dept = user['department_token']
        users_by_age = users_by_dept.setdefault(dept, dict())
        users_by_age.setdefault(hours, list()).append((age, user))
    all_clipped = get_all_clipped()
    all_depts = list(set(all_clipped.keys()))# + users_by_dept.keys()))
    for dept in sorted(all_depts):
        print '----------------- %s -----------------' % dept
        if show_active:
            print '   Who is Active:'
            users_by_age = users_by_dept.get(dept, dict())
            for hours in reversed(sorted(users_by_age.keys())):
                if hours > 3:
                    continue
                print '      <%d Hours Ago' % hours 
                for age, user in reversed(sorted(users_by_age[hours])):
                    age_str = api.get_duration_str(age)
                    if age == 0:
                        age_str = 'Now'
                    print '         % 14s - %20s (%s)' % (user['username'], user['real_name'], age_str)
        if show_clipped:
            print '   Who Is Clipped:'
            for user in all_clipped.get(dept, ['NONE']):
                print '        %s' % user

if __name__ == '__main__':
    main()