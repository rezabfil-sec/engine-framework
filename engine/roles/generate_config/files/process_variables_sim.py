#!/usr/bin/python3

# Reusably processes variables by calculating additional parameters that are
# required for the generation of simulation ini files, based on existing
# parameters from scenario variable files.

def cbs_max_interference_size(idle_slope, high, bitrate):
    """
        Calculates the maxInterferenceSize

        INET's Ieee8021qCreditBasedShaper does not allow to directly specify a
        maxCredit. Instead it calculates it via the formula 'maxCredit =
        dropUnit(maxInterferenceSize) * dropUnit(idleSlope / bitrate)'.
        maxCredit has thus to be adapted via the maxInterferenceSize parmeter,
        which is calculated here, based on the given parameters.

        Parameters
        ----------
        idle_slope : int
            idleSlope in kbps (as required in ansible variable files)
        high : int
            high aka maxCredit in bytes (as required in ansible variable files)
        bitrate : int, optional
            bitrate of the link where the CBS should be applied in kbps

        Returns
        -------
        maxInterferenceSize
            maxInterferenceSize in bytes to achieve the given maxCredit / high
    """
    max_interference_size = high * bitrate / idle_slope
    return int(max_interference_size)

def prio2queue_mapping(queues):
    """
        Calculates the prio to queue mapping

        INETs's PcpTrafficClassClassifier requires a matrix, mapping pcp values
        (i.e. priorities) to traffic classes (i.e. queues). EnGINE's variable
        files have a dict with prios per queues, which is processed here to
        yield the required mapping.

        Parameters
        ----------
        queues : dict
            dict with queue number (plus 1) as keys and dicts as values, which
            in turn have an entry with "prio" as key and a list of ints / "*" 
            (for default queue) as value

        Returns
        -------
        mapping
            8x8 matrix mapping priorities (row) to queues (column)
    """
    default_queue = None
    for queues_key, queues_value in queues.items():
        if "*" in queues_value['prio']:
            default_queue = int(queues_key)-1
    assert default_queue != None
    mapping = []
    for priority in range(8):
        q = default_queue
        for queues_key, queues_value in queues.items():
            if priority in queues_value['prio']:
                q = int(queues_key)-1
        mapping.append([q]*8)
    return mapping

def schedule(num_queues, sched):
    """
        Transforms the taprio schedule into a periodic per queue schedule

        Instead of using open gates per schedule item, as required for EnGINE's
        taprio schedule, INETs's PeriodicGate class requires a periodic
        schedule per gate instance with an additional offset that indicates
        where the gate should initially start.

        Parameters
        ----------
        sched : list of dictionaries
            list of dictionaries, each providing a duration (in us) and a list
            of queues that shall be permitted for this duration (using queue
            index + 1, 0 for no queues)

        Returns
        -------
        list of dictionaries, storing the respective durations (list of gate 
        state durations (not initiallyOpen)) and offset (the respective offset)
        per queue
        
    """
    durations = [[] for _ in range(num_queues)]
    offset = [0]*num_queues

    is_open = [False]*num_queues
    time = [0]*num_queues

    ignore = [False]*num_queues # whether the queue should be ignored, i.e. no periodical gate should be installed (there might be problems if there is a gate with a single durations entry: see https://github.com/inet-framework/inet/pull/776)

    def update_state(queue, state, duration):
        if not state == is_open[queue]:
            durations[queue].append(time[queue])
            is_open[queue] = state
            time[queue] = 0
        time[queue] += duration

    for s in sched:
        queue = s['queue']
        for q in range(num_queues):
            if 0 in queue:
                update_state(q, False, s['duration'])
            elif q + 1 in queue:
                update_state(q, True, s['duration'])
            else:
                update_state(q, False, s['duration'])
    for q in range(num_queues):
        if is_open[q]:
            if durations[q][0] == 0 and len(durations[q]) > 1:
                durations[q][0] = durations[q][-1] # replace - 'durations[q][0] == 0' is in branch condition
                durations[q][1] += time[q]
                offset[q] = durations[q][-1] + time[q]
                durations[q].pop(-1)
            else:
                durations[q].append(time[q])
                if durations[q][0] == 0:
                    ignore[q] = True
        elif time[q]!=0:
            while len(durations[q]) < 2:
                durations[q].append(0)
                ignore[q] = True
            durations[q][0]+=time[q]
            offset[q] = time[q]
    res = []
    for d, o, i in zip(durations, offset, ignore):
        res.append({'durations': d, 'offset': o, 'ignore': i})
    return res
