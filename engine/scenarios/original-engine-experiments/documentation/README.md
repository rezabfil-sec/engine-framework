# Documentation Scenario

This scenario folder contains examples and extensive comments to understand how scenarios are configured in this configuration format.

Possible variants are divided by a new line and `//`
Optional arguments are in brackets `()`

This scenario folder is not executable!
(because of variants and optional arguments)

# TSN configuration format introduction

The original experiments (on architecture 0.5) are not conducted in its entirety in future architectures.
The results in the architecture 0.5 helped us to identify relevant configurations and
omit parameters and configurations that are not interesting/important.

In the first couple of TSN configurations we tried out many different combinations of hardware
queue mappings to answer the following questions:
1. Does the order of the hardware queues change the outcome?
2. How is the behavior when mapping multiple hardware queues to one traffic class?
3. All kind of combinations for the above two, do they make a difference?

The answer to all of them were -> no (for the Intel i210)

The main outcome of the 0.5 experiments:
- Offload only works on hardware queues 0 + 1 (queues 1+2)
- Do not use offload at all, when using more than the first two (1+2) queues, otherwise the other two queues will behave strangely
- (Apart from offloading) The order and number of queue mappings does no influence the outcome

Based on these findings we designed the scenario format in such a ways that it
makes the configuration easier and hides complexity. The mapping from priorities to traffic
classes to hardware queues to queue configurations is hidden and a simple queue
and priority based configuration is possible.

Hardware queues is not the same as tsn.queues. The tsn.queues are a mix of hardware queues,
traffic classes and priority to traffic class mapping.

The mapping of the queues to the hardware queues is fixed and based on the number
of tsn.queues. The mapping is hard-coded in roles/network/templates/taprio.j2 + cbs_mqprio.j2.
<num tsn_queues>: <tsn.queue>=<hw.queues>
1:  1 = 0+1+2+3                 (all hw queues are mapped to the same queue)
2:  1 = 0+1; 2 = 2+3            (hw queues are equally split)
3:  1 = 0; 2 = 1; 3 = 2+3       (last tsn queue has two hw queues)
4:  1 = 0; 2 = 1; 3 = 2; 4 = 3  (every tsn queues has one hw queue)

Therefore it is not possible to conduct all original experiments as for some of them
the hidden complexity needs to be made available in the configuration format.
