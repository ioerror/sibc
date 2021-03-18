from random import SystemRandom
from pkg_resources import resource_filename

from functools import reduce
from math import floor, sqrt

from sidh.math import isequal, bitlength, hamming_weight, cswap, sign
from sidh.constants import parameters

class Strategy(object):
    def __init__(self, prime, tuned, curve, formula):
        self.random = SystemRandom()

        # In order to achieve efficiency, the optimal strategies and their cost are saved in two global dictionaries (hash tables)
        self.S = {1: {}}  # Initialization of each strategy
        self.C = {1: {}}  # Initialization of the costs: 0.

        self.curve = curve
        self.prime = prime
        self.formula = formula
        self.formula_name = formula.name
        self.field = self.curve.field
        self.tuned = tuned
        self.L = curve.L
        self.SIDp = reduce(lambda x, y: x + y, [[self.curve.Lp[i]] * self.curve.Ep[i] for i in range(0, self.curve.np, 1)])
        self.SIDm = reduce(lambda x, y: x + y, [[self.curve.Lm[i]] * self.curve.Em[i] for i in range(0, self.curve.nm, 1)])

        self.c_xmul = self.curve.c_xmul
        n = curve.n
        for i in range(n):
            self.S[1][tuple([self.L[i]])] = []
            # Strategy with a list with only one element (a small odd prime number l_i)
            self.C[1][tuple([self.L[i]])] = self.formula.c_xisog[i]
            # For catching the weigth of horizontal edges of the form [(0,j),(0,j+1)]
        for i in range(2, len(self.SIDp) + len(self.SIDm) + 1):
            self.C[i] = {}
            self.S[i] = {}

        # Reading public generators points
        f = open(resource_filename('sidh', 'data/gen/' + prime))

        # x(PA), x(QA) and x(PA - QA)
        PQA = f.readline()
        PQA = [int(x, 16) for x in PQA.split()]
        self.PA = [self.field(PQA[0:2]), self.field(1)]
        self.QA = [self.field(PQA[2:4]), self.field(1)]
        self.PQA= [self.field(PQA[4:6]), self.field(1)]

        # x(PB), x(QB) and x(PB - QB)
        PQB = f.readline()
        PQB = [int(x, 16) for x in PQB.split()]
        self.PB = [self.field(PQB[0:2]), self.field(1)]
        self.QB = [self.field(PQB[2:4]), self.field(1)]
        self.PQB= [self.field(PQB[4:6]), self.field(1)]

        f.close()

        # These are for nonlocal in the pk/dh functions
        self.PA_b, self.QA_b, self.PQA_b = None, None, None
        self.PB_a, self.QB_a, self.PQB_a = None, None, None

        f_name = 'data/strategies/bsidh-'+prime+'-'+formula.name+('-classical','-suitable')[self.tuned]
        try:
            f = open(resource_filename('sidh', f_name))
            # Corresponding to the list of Small Isogeny Degree, Lp := [l_0, ...,
            # l_{n-1}] [We need to include case l=2 and l=4]
            tmp = f.readline()
            tmp = [int(b) for b in tmp.split()]
            self.Sp = list(tmp)
            # Corresponding to the list of Small Isogeny Degree, Lm := [l_0, ...,
            # l_{n-1}]
            tmp = f.readline()
            tmp = [int(b) for b in tmp.split()]
            self.Sm = list(tmp)
            f.close()
        except IOError:
            print("// Strategies to be computed")
            # List of Small Isogeny Degree, Lp := [l_0, ..., l_{n-1}] [We need to
            # include case l=2 and l=4]
            self.Sp, Cp = dynamic_programming_algorithm(self.SIDp[::-1], len(self.SIDp))
            # List of Small Isogeny Degree, Lm := [l_0, ..., l_{n-1}]
            self.Sm, Cm = dynamic_programming_algorithm(self.SIDm[::-1], len(self.SIDm))
            f = open(f_name, 'w')
            f.writelines(' '.join([str(tmp) for tmp in self.Sp]) + '\n')
            f.writelines(' '.join([str(tmp) for tmp in self.Sm]) + '\n')
            f.close()
        ######################################################################################################################

    def dynamic_programming_algorithm(self, L, n):
        """
        dynamic_programming_algorithm():
        inputs: the list of small odd primes to be processed and its length
        output: the optimal strategy and its cost of the input list of small odd primes
        """
        # If the approach uses dummy operations, to set DUMMY = 2.0;
        # otherwise, to set DUMMY = 1.0 (dummy free approach);

        if len(L) != n:

            # If the list of prime numbers doesn't have size n, then we return [],-1
            print(
                "error:\tthe list of prime numbers has different size from %d."
                % n
            )
            return [], -1
        else:

            # Assuming #L = n, we proceed.
            get_neighboring_sets = lambda L, k: [
                tuple(L[i : i + k]) for i in range(n - k + 1)
            ]  # This function computes all the k-tuple: (l_1, l_2, ..., l_{k)),
            # (l_2, l_3, ..., l_{k+1)), ..., (l_{n-k}, l_{n-k+1, ..., l_{n)).
            for i in range(2, n + 1):

                for Tuple in get_neighboring_sets(L, i):

                    if self.C[i].get(Tuple) is None:

                        alpha = [
                            (
                                b,
                                self.C[len(Tuple[:b])][Tuple[:b]]
                                + self.C[  # Subtriangle on the right side with b leaves
                                    len(Tuple[b:])
                                ][
                                    Tuple[b:]
                                ]
                                + 1.0  # Subtriangle on the left side with (i - b) leaves
                                * sum(
                                    [
                                        self.c_xmul[
                                            self.formula.L.index(t)
                                        ]
                                        for t in Tuple[:b]
                                    ]
                                )
                                + 1.0  # Weights corresponding with vertical edges required for connecting the vertex (0,0) with the subtriangle with b leaves
                                * sum(
                                    [
                                        self.formula.c_xeval[
                                            self.formula.L.index(t)
                                        ]
                                        for t in Tuple[b:]
                                    ]
                                ),
                            )
                            for b in range(1, i)
                        ]
                        b, self.C[i][Tuple] = min(
                            alpha, key=lambda t: self.curve.measure(t[1])
                        )  # We save the minimal cost corresponding to the triangle with leaves Tuple
                        self.S[i][Tuple] = (
                            [b]
                            + self.S[i - b][Tuple[b:]]
                            + self.S[b][Tuple[:b]]
                        )  # We save the optimal strategy corresponding to the triangle with leaves Tuple

            return (
                self.S[n][tuple(L)],
                self.C[n][tuple(L)],
            )  # The weight of the horizontal edges [(0,n-1),(0,n)] must be equal to c_xisog[self.formula.L.index(L[0])].

    def random_scalar_A(self): return self.random.randint(0, self.curve.p + 1)
    def random_scalar_B(self): return self.random.randint(0, self.curve.p - 1)

    def strategy_at_6_A(self, sk_a):
        #nonlocal PB_a, QB_a, PQB_a
        A = [self.curve.field(8), self.curve.field(4)]
        Ra = self.curve.Ladder3pt(sk_a, self.PA, self.QA, self.PQA, A)
        pk_a, self.PB_a, self.QB_a, self.PQB_a = self.evaluate_strategy(
            True,
            self.PB,
            self.QB,
            self.PQB,
            A,
            Ra,
            self.SIDp[::-1],
            self.Sp,
            len(self.SIDp)
        )
        return pk_a

    def strategy_at_6_B(self, sk_b):
        #nonlocal PA_b, QA_b, PQA_b
        A = [self.curve.field(8), self.curve.field(4)]
        Rb = self.curve.Ladder3pt(sk_b, self.PB, self.QB, self.PQB, A)
        pk_b, self.PA_b, self.QA_b, self.PQA_b = self.evaluate_strategy(
            True,
            self.PA,
            self.QA,
            self.PQA,
            A,
            Rb,
            self.SIDm[::-1],
            self.Sm,
            len(self.SIDm)
        )
        return pk_b

    def strategy_A(self, sk_a, pk_b):
        # sk here is alice's secret key
        # pk_b here is from bob (not processed by coeff)
        #nonlocal PA_b, QA_b, PQA_b
        assert self.curve.issupersingular(pk_b), "non-supersingular input curve"
        RB_a = self.curve.Ladder3pt(sk_a, self.PA_b, self.QA_b, self.PQA_b, pk_b)
        ss_a, _, _, _ = self.evaluate_strategy(
            False,
            self.PB,
            self.QB,
            self.PQB,
            pk_b,
            RB_a,
            self.SIDp[::-1],
            self.Sp,
            len(self.SIDp)
        )
        return ss_a

    def strategy_B(self, sk_b, pk_a):
        # sk_b here is bob's secret key
        # pk_a here is from alice (not processed by coeff)
        #nonlocal PB_a, QB_a, PQB_a
        assert self.curve.issupersingular(pk_a), "non-supersingular input curve"
        RA_b = self.curve.Ladder3pt(sk_b, self.PB_a, self.QB_a, self.PQB_a, pk_a)
        ss_b, _, _, _ = self.evaluate_strategy(
            False,
            self.PA,
            self.QA,
            self.PQA,
            pk_a,
            RA_b,
            self.SIDm[::-1],
            self.Sm,
            len(self.SIDm)
        )
        return ss_b

    def evaluate_strategy(self, EVAL, S_in, T_in, ST_in, E, P, L, strategy, n):
        '''
        evaluate_strategy():
                 primes;
        output : the projective Montgomery constants a24:= a + 2c and c24:=4c where E': y^2 = x^3 + (a/c)*x^2 + x
                     is E / <P>
        '''

        ramifications = []
        moves = [
            0
        ]  # moves: this list determines whether an isogeny construction must be performed
        k = 0  # k: current element of the strategy

        ramifications.append(list(P))
        E_i = list(E)

        if EVAL:
            # Public points to be evaluated
            S_out = list(
                S_in
            )  # x(S) should be a torsion point with not common factors in L
            T_out = list(
                T_in
            )  # x(T) should be a torsion point with not common factors in L
            ST_out = list(
                ST_in
            )  # x(S - T) should be a torsion point with not common factors in L
        else:
            S_out = None
            T_out = None
            ST_out = None

        assert len(strategy) == (n - 1)
        for i in range(len(strategy)):

            pos = self.L.index(
                L[n - 1 - i]
            )  # Current element of self.L to be required

            # Reaching the vertex (n - 1 - i, i)
            # Vertical edges (scalar multiplications)
            prev = sum(moves)
            while prev < (n - 1 - i):

                moves.append(
                    strategy[k]
                )  # Number of vertical edges to be performed
                T = list(ramifications[-1])  # New ramification
                for j in range(prev, prev + strategy[k], 1):
                    T = self.curve.xmul(T, E_i, self.L.index(L[j]))

                ramifications.append(list(T))
                prev += strategy[k]
                k += 1

            # Deciding which velu variant will be used
            if self.formula_name != 'tvelu':
                # This branchs corresponds with the use of the new velu's formulaes

                if self.tuned:
                    self.formula.set_parameters_velu(self.formula.sJ_list[pos], self.formula.sI_list[pos], pos)

                else:
                    # -------------------------------------------------------------
                    # Parameters sJ and sI correspond with the parameters b and b' from example 4.12 of https://eprint.iacr.org/2020/341
                    # These paramters are required in self.formula.kps, self.formula.xisog, and self.formula.xeval
                    if self.L[pos] <= 4:
                        b = 0
                        c = 0
                    else:
                        b = int(floor(sqrt(self.L[pos] - 1) / 2.0))
                        c = int(floor((self.L[pos] - 1.0) / (4.0 * b)))

                    if self.formula_name != 'tvelu':
                        self.formula.set_parameters_velu(b, c, pos)

            # Kernel Points computation
            self.formula.kps(ramifications[-1], E_i, pos)

            # Isogeny construction
            ramifications[-1][0], E_i[0] = cswap(
                ramifications[-1][0], E_i[0], self.L[pos] == 4
            )
            ramifications[-1][1], E_i[1] = cswap(
                ramifications[-1][1], E_i[1], self.L[pos] == 4
            )
            C_i = self.formula.xisog(E_i, pos)
            ramifications[-1][0], E_i[0] = cswap(
                ramifications[-1][0], E_i[0], self.L[pos] == 4
            )
            ramifications[-1][1], E_i[1] = cswap(
                ramifications[-1][1], E_i[1], self.L[pos] == 4
            )

            # Now, we proceed by perform horizontal edges (isogeny evaluations)
            for j in range(0, len(moves) - 1, 1):

                if (
                    self.formula_name == 'tvelu'
                    or (
                        self.formula_name == 'hvelu'
                        and self.L[pos] <= self.formula.HYBRID_BOUND
                    )
                    or (self.L[pos] == 4)
                ):
                    ramifications[j] = self.formula.xeval(ramifications[j], pos)
                else:
                    ramifications[j] = self.formula.xeval(ramifications[j], E_i)

            if EVAL:
                # Evaluating public points
                if (
                    self.formula_name == 'tvelu'
                    or (
                        self.formula_name == 'hvelu'
                        and self.L[pos] <= self.formula.HYBRID_BOUND
                    )
                    or (self.L[pos] == 4)
                ):

                    S_out = self.formula.xeval(S_out, pos)
                    T_out = self.formula.xeval(T_out, pos)
                    ST_out = self.formula.xeval(ST_out, pos)
                else:

                    S_out = self.formula.xeval(S_out, E_i)
                    T_out = self.formula.xeval(T_out, E_i)
                    ST_out = self.formula.xeval(ST_out, E_i)

            # Updating the Montogmery curve coefficients
            E_i = [self.field(C_i[0]), self.field(C_i[1])]

            moves.pop()
            ramifications.pop()

        pos = self.L.index(L[0])  # Current element of self.L to be required

        if self.formula_name != 'tvelu':
            # This branchs corresponds with the use of the new velu's formulaes

            if self.tuned:
                self.formula.set_parameters_velu(self.formula.sJ_list[pos], self.formula.sI_list[pos], pos)

            else:
                # -------------------------------------------------------------
                # Parameters sJ and sI correspond with the parameters b and b' from example 4.12 of https://eprint.iacr.org/2020/341
                # These paramters are required in self.formula.kps, self.formula.xisog, and self.formula.xeval
                if self.L[pos] <= 4:
                    b = 0
                    c = 0
                else:
                    b = int(floor(sqrt(self.L[pos] - 1) / 2.0))
                    c = int(floor((self.L[pos] - 1.0) / (4.0 * b)))

                self.formula.set_parameters_velu(b, c, pos)

        # Kernel Points computations
        self.formula.kps(ramifications[0], E_i, pos)

        # Isogeny construction
        ramifications[0][0], E_i[0] = cswap(
            ramifications[0][0], E_i[0], self.L[pos] == 4
        )
        ramifications[0][1], E_i[1] = cswap(
            ramifications[0][1], E_i[1], self.L[pos] == 4
        )
        C_i = self.formula.xisog(E_i, pos)
        ramifications[0][0], E_i[0] = cswap(
            ramifications[0][0], E_i[0], self.L[pos] == 4
        )
        ramifications[0][1], E_i[1] = cswap(
            ramifications[0][1], E_i[1], self.L[pos] == 4
        )

        if EVAL:
            # Evaluating public points
            if (
                self.formula_name == 'tvelu'
                or (self.formula_name == 'hvelu' and self.L[pos] <= self.formula.HYBRID_BOUND)
                or (self.L[pos] == 4)
            ):

                S_out = self.formula.xeval(S_out, pos)
                T_out = self.formula.xeval(T_out, pos)
                ST_out = self.formula.xeval(ST_out, pos)

            else:

                S_out = self.formula.xeval(S_out, E_i)
                T_out = self.formula.xeval(T_out, E_i)
                ST_out = self.formula.xeval(ST_out, E_i)

        # Updating the Montogmery curve coefficients
        E_i = [self.field(C_i[0]), self.field(C_i[1])]

        return E_i, S_out, T_out, ST_out

