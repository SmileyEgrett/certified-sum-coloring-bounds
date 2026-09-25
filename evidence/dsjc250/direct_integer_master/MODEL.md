# Complete stable-set/Ferrers integer master

The optimization inputs are only the DIMACS graph and its freshly enumerated
nonempty stable sets. No known feasible colouring, optimum, conditional-envelope
certificate, profile frontier, or chromatic bound is used.

For each stable set S introduce a binary x_S. For every graph vertex v impose
`sum_{S containing v} x_S = 1`. Selected sets therefore partition the vertices
into stable classes. Conversely, every proper colouring, with empty classes
discarded, supplies one such exact cover. Repeated equal nonempty classes are
impossible in a partition, so binary set variables lose no valid colouring.

For t=1,...,alpha let q_t be the number of selected sets of size at least t.
It is represented implicitly by `sum_{|S|>=t} x_S`. Introduce n div t continuous
variables y_(t,j), each between zero and one, and one equation per layer:

    sum_j y_(t,j) - sum_{|S|>=t} x_S = 0.

The bound q_t <= floor(n/t) follows from disjointness: q_t selected classes of
size at least t use at least t*q_t of the n vertices. It is unrelated to any
incumbent. No ordering constraints on the y variables are necessary.

Minimize `sum_(t,j) j*y_(t,j)`. For integer q_t, an exchange argument shows that
the cheapest feasible cells are the first q_t cells: if an earlier cell is not
full and a later cell is positive, moving mass earlier decreases the objective.
Thus the minimum layer contribution is q_t*(q_t+1)/2. The cells may be continuous;
integrality of q_t comes from the binary x variables.

Sort the selected class sizes s_1 >= ... >= s_k. Their optimally relabelled
colouring sum is `sum_i i*s_i`. Counting this Ferrers diagram by layers gives
`sum_t sum_{i=1}^{q_t} i = sum_t q_t*(q_t+1)/2`, exactly the model objective at
an optimum. The formulation is consequently an exact integer formulation of
minimum-sum colouring, without a restriction on the number of classes.

The standalone LP calibration changes only x integrality to continuous. Its
value is the relaxation of this particular unit-cell formulation. It is not
identified with the ordinary fractional chromatic number or a different sum LP.
The subsequent MIP starts from a new process and imports no LP basis or solution.

## Completeness and model checking

The generator recursively appends increasing vertex labels compatible with all
previous choices, using filtered candidates. It enumerates all nonempty stable
sets without stopping at a presupposed maximum size.

The separate checker establishes completeness using a different certificate:
all singletons are present; every listed set is stable, sorted and unique; and
every compatible larger last vertex extends a listed set to another listed set.
Any missing stable set would have a shortest missing sorted prefix, contradicting
the singleton or extension checks. This also rules out all sizes above the
largest listed stable set, rather than merely failing to find a size-six set.

The checker independently reconstructs the expected MPS data from the graph and
stable-set file. It requires exact agreement of row types, every matrix and
objective coefficient, right-hand sides, variable bounds, and integrality.
There is no hidden objective cutoff or omitted class-size layer.

## Evidence boundary

An independently checked returned colouring proves a feasible upper bound.
A HiGHS status of Optimal records conventional floating-point MIP computational
closure. This pipeline does not emit or verify a formal lower-bound proof, and
neither its log nor its exact formulation is presented as such a proof.
