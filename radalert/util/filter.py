"""
Simple data filtering module.

Provides functions and classes that implement FIR and IIR filters.
"""

import math


def mean_arithmetic(values):
    """Get the arithmetic mean of the input list."""
    if len(values) == 0:
        return None
    return sum(values) / len(values)


def mean_geometric(values):
    """Get the geometric mean of the input list."""
    if len(values) == 0:
        return None
    mean = values[0]
    for i in range(1, len(values)):
        mean = math.pow(values[i] * math.pow(mean, i-1), 1/i)
    return mean


def mean_quadradic(values):
    """Get the quadradic mean / RMS value of the input list."""
    if len(values) == 0:
        return None
    squares = map(lambda x: x*x, values)
    mean = mean_arithmetic(squares)
    return math.pow(mean, 0.5)


class FIRFilter:
    """
    Implementation of an FIR (finite impulse response) filter.

    This filter returns a filtered value based on a finite list of
    the last "n" input values. The exact filtering function can
    be specified when the filter is initalized.
    """

    def __init__(self, size, function=mean_arithmetic):
        """
        Create an FIR filter with the specified size and filtering function.

        The returned filter will keep track of the last `size` values
        given to it and apply the given `function` to those values
        whenever the `.value` property is accessed. The default filter
        function is simply the arithmetic mean.
        """
        self.size = size
        self.values = []
        self.function = function

    def iterate(self, value):
        """
        Add the specified value into the filter and return the updated
        filtered value.
        """
        self.values.append(value)
        if len(self.values) > self.size:
            self.values.pop(0)
        return self.value

    @property
    def value(self):
        """
        Get the current filtered value.

        Applies the current function to the set of values and returns
        the result.
        """
        return self.function(self.values)


class IIRFilter:
    """
    Implementation of an IIR (infinite impulse response) filter.

    This filter has an exponential decay response which can be
    characterized with any of several potential constants. The two
    most common being the time-constant (time to decay by a factor
    of 1/e) and the half-life (time to decay by a factor of 1/2).

    This class provides several constructors and utility methods
    for working with the various representations.

    Once constructed, you can `iterate()` the filter with input
    values and observe the filter output.
    """

    def __init__(self, coefficient):
        """
        Create an IIR filter with the specified decay coefficient.

        The decay coefficient represents the fraction of the original
        value which is preserved after each iteration. It leads to the
        most natural way to implement such a filter, though other more
        familiar representations can also be used by calling the various
        `create_from_xxx` functions instead.
        """
        self.coefficient = coefficient
        self.value = None

    def iterate(self, value):
        """
        Mix the provided value into the IIR filter, advancing its state
        by one iteration.
        """
        if self.value is None:
            self.value = value
        self.value *= self.coefficient
        self.value += value * (1-self.coefficient)
        return self.value

    @staticmethod
    def create_from_time_constant(iterations):
        """
        Create an IIR filter with the specificied time-constant.

        The time-constant defines how many iterations it will take for
        the filter to decay to a value of 1/e times its original value.
        """
        coefficient = IIRFilter.time_constant_to_coefficient(iterations)
        return IIRFilter(coefficient)

    @staticmethod
    def create_from_half_life(iterations):
        """
        Create an IIR filter with the specified half-life.

        The half-life defines how many iterations it will take for the
        filter to decay to a value of 1/2 times its original value.
        """
        coefficient = IIRFilter.half_life_to_coefficient(iterations)
        return IIRFilter(coefficient)

    @staticmethod
    def create_from_decay_params(target, iterations):
        """
        Create an IIR filter with the specified decay parameters.

        The decay parameters define how many iterations it will take for
        the filter to decay to a value of 1/target times its original
        value.
        """
        coefficient = IIRFilter.decay_params_to_coefficient(target, iterations)
        return IIRFilter(coefficient)

    @staticmethod
    def time_constant_to_coefficient(iterations):
        """
        Convert a time-constant to a decay coefficient.

        Return the coefficient necessary to cause a value to decay to
        a value of 1/e times its original value in the number of
        specified iterations.
        """
        return math.exp(-1/iterations)

    @staticmethod
    def coefficient_to_time_constant(coefficient):
        """
        Convert a decay coefficient to a time-constant.

        Return the number of iterations it will take a filter with the
        given coefficient to decay to a value of 1/e times its original
        value.
        """
        return -1/math.log(coefficient)

    @staticmethod
    def half_life_to_coefficient(iterations):
        """
        Convert a half-life to a decay coefficient.

        Return the coefficient necessary to cause a value to decay to
        a value of 1/2 times its original value in the number of
        specified iterations.
        """
        return math.exp(-math.log(2)/iterations)

    @staticmethod
    def coefficient_to_half_life(coefficient):
        """
        Convert a decay coefficient to a half-life.

        Return the number of iterations it will take a filter with the
        given coefficient to decay to a value of 1/2 times its original
        value.
        """
        return -math.log(2)/math.log(coefficient)

    @staticmethod
    def decay_params_to_coefficient(target, iterations):
        """
        Convert decay parameters to a decay coefficient.

        Return the coefficient necessary to cause a value to decay to
        a value of target times its original value in the number of
        specified iterations.
        """
        return math.exp(-math.log(1/target)/iterations)

    @staticmethod
    def coefficient_to_decay_iters(coefficient, target):
        """
        Convert a coefficient to its "iterations" decay parameter.

        Return the number of iterations it will take a filter with the
        given coefficient to decay to a value of 1/target times its
        original value.
        """
        return -math.log(1/target)/math.log(coefficient)
