from getpass import getpass
import jmapfilter


password = getpass()

global_handler = jmapfilter.Handler('me@example.com', password)


def filter_for_test(message):
    to_list = message['to']
    return 'me+test@example.com' in [to['email'] for to in to_list]


def action_mark_seen_and_delete(handler, m):
    handler.mark_seen(m)
    handler.flag(m)
    handler.move_to_trash(m)


apply_filters = [
    action_mark_seen_and_delete(global_handler, m)
    for m in global_handler.client.cache_messages
    if filter_for_test(m)
]

global_handler.apply_batch()
