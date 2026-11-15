"""Shared helpers for the staff work queues: A08 review before dispatch and A09 support tickets.

Both queues work the same way:
- a list page with tabs (one per state), the items grouped into sections in working order;
- a one-at-a-time page with ← / → arrows through the same queue and a link back to the list;
- after a decision, staff land on the next item that still needs them.

The templates that go with this are staffpanel/queue_list.html (the list) and
staffpanel/_queue_nav.html plus static/js/queue_keys.js (the arrows on the one-at-a-time page).
"""
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


def group_by(items, key, label):
    """[(label, [items])] for runs of items with the same key. The items must already be sorted,
    so the order inside each group is the queue order."""
    groups = []
    for item in items:
        k = key(item)
        if not groups or groups[-1][0] != k:
            groups.append((k, []))
        groups[-1][1].append(item)
    return [(label(k), group) for k, group in groups]


def queue_nav(queue, item, url_name, query=""):
    """Arrows for the one-at-a-time page: where this item sits in its queue and its neighbours.
    query (e.g. "?sort=risk") is kept on the links so the arrows follow the order the list showed."""
    ids = [i.pk for i in queue]
    if item.pk not in ids:  # e.g. an order that has since been dispatched
        return {"position": None, "size": len(ids), "prev_url": None, "next_url": None}
    i = ids.index(item.pk)
    return {
        "position": i + 1, "size": len(ids),
        "prev_url": reverse(url_name, args=[ids[i - 1]]) + query if i > 0 else None,
        "next_url": reverse(url_name, args=[ids[i + 1]]) + query if i + 1 < len(ids) else None,
    }


def go_to_next(request, done_pk, waiting_ids, detail_url, list_url, empty_message, query=""):
    """After a decision on done_pk, open the next item still waiting, in queue order after it
    (wrapping round to the start). waiting_ids is the queue as it was before the decision."""
    left = [pk for pk in waiting_ids if pk != done_pk]
    later = waiting_ids[waiting_ids.index(done_pk) + 1:] if done_pk in waiting_ids else []
    nxt = next((pk for pk in later if pk in left), left[0] if left else None)
    if nxt is None:
        messages.success(request, empty_message)
        return redirect(reverse(list_url) + query)
    return redirect(reverse(detail_url, args=[nxt]) + query)
