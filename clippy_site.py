
import re
import clippy_api as api

REMOVE_KEYS = ['profiles_url', 'bigger_pic_url', 'tiny_pic_url', 'normal_pic_url', 'website', 'bio']
DROP_USERS = ['melendt']

def init_default_clipped_users():
    api.load_all_users()
    for users in api.USERS_BY_DEPT.itervalues():
        dsupes = [u for u in users if 'supe' in u['job_title'].lower()]
        supervisor = dsupes[0] if dsupes else users[0]
        dept_lbl = supervisor['department_name']
        real_name = supervisor['full_name']
        print '% 20s : %s' % (dept_lbl, real_name)
        api.clip_user(supervisor, None, None)

def init_all_users_reference():
    import json
    from pipe_utils.user_utils import RUser
    all_user_data = dict()
    for ruser in RUser.get_all():
        user_data = dict(ruser.user_data)
        if ruser.username in DROP_USERS:
            continue
        username = user_data.pop('user_name', None)
        dept = user_data.pop('department_name', None)
        full_name = user_data.get('full_name', None)
        for key in REMOVE_KEYS:
            user_data.pop(key, None)
        if username == 'nhurm':
            dept = 'Technical Direction'
        if dept == 'Look Dev':
            dept = 'Surfacing'
        if not dept:
            dept = 'Other'
        user_data['username'] = username
        user_data['department'] = dept
        user_data['real_name'] = full_name
        dept = re.sub('[^a-zA-Z0-9_]+', '_', dept).lower()
        user_data['department_token'] = dept
        # remove None entries
        for key, value in user_data.items():
            if value is None:
                user_data.pop(key)
        all_user_data[username] = user_data
    encoder = json.JSONEncoder(indent=2, sort_keys=True)
    json_str = encoder.encode(all_user_data)
    open(api.ALL_USERS_PATH, 'w').write(json_str)

def add_site_specific_msg_kwargs(msg_kwargs):
    """
    Adds variables which can appear in event messages that site specific.
    """
    try:
        from pipe_core import PipeContext, Project, Discipline
    except ImportError:
        return
    disc_map = {
        Discipline.LAY : 'doing layout',
        Discipline.EDIT : 'editing',
        Discipline.ANI : 'animating',
        Discipline.ANIFIN: 'finaling animation',
        Discipline.ENV: 'making environments',
        Discipline.FX: 'doing effects',
        Discipline.FUR: 'simulating fur',
        Discipline.FUR: 'doing TD stuff',
    }
    ctx = PipeContext.from_env()
    disc = 'doing nothing'
    if ctx.discipline:
        msg_kwargs['discipline'] = disc_map.get(disc, disc.label).lower()
        msg_kwargs['context'] = ctx.short_name
    project = Project.current()
    if project and project.title:
        msg_kwargs['project'] = project.title

