import matplotlib.pyplot as plt
try:
    import ujson as json
except ImportError:
    import json
from datetime import datetime
import pytz
import numpy


with open('../testdata/messages.json') as messages_json_file:
    messages = json.load(messages_json_file)

for order_type in ['open', 'done', 'change', 'match', 'received']:
    msgs = [datetime.strptime(message['time'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.UTC) for message in messages
                     if message['type'] == order_type]
    msgs = numpy.diff(msgs)
    msgs = [float(sec.microseconds) for sec in msgs if float(sec.microseconds) < 50000]
    if msgs:
        n, bins, patches = plt.hist(msgs, 100, alpha=0.50, label=order_type, stacked=True)


plt.xlabel('Time between messages')
plt.ylabel('Count')
plt.grid(True)
plt.legend(loc='upper right')

plt.savefig('foo.png')
plt.close()
