"""
One-dimensional Kalman filter implementation for tracking a single variable (e.g., price).
"""
from typing import Optional

class KalmanFilter1D:
    """
    A simple 1D Kalman Filter for sequential data.

    This filter can be used to estimate and smooth a single variable
    (such as a price or signal).
    It accounts for process noise and measurement noise.
    """
    def __init__(self,
                 process_variance: float,
                 measurement_variance: float,
                 initial_value: float = 0.0,
                 initial_estimate_error: float = 1.0) -> None:
        """
        Initialize the 1D Kalman Filter.

        Parameters:
            process_variance (float): Variance of the underlying process (Q).
            Higher values allow the estimate to change more rapidly.
            measurement_variance (float): Variance of the observation noise (R).
            Lower values trust the observations more.
            initial_value (float): Initial estimated value.
            initial_estimate_error (float): Initial estimate uncertainty (P).
            Larger values indicate less confidence in the initial estimate.
        """
        # State estimate
        self.x: float = initial_value
        # Estimate covariance (uncertainty)
        self.P: float = initial_estimate_error
        # Noise parameters
        self.Q: float = process_variance
        self.R: float = measurement_variance

    def update(self, measurement: float) -> float:
        """
        Incorporate a new measurement into the filter and update the state estimate.

        Performs a prediction-update cycle:
        - Prediction: increases the estimate uncertainty by process variance.
        - Update: adjusts the estimate based on the measurement and its uncertainty.

        Parameters:
            measurement (float): The new observed value to incorporate.

        Returns:
            float: The updated state estimate after incorporating the measurement.
        """
        # Prediction step: project the state ahead (for 1D, state remains the same)
        # and increase uncertainty
        self.P += self.Q

        # Kalman gain
        K: float = self.P / (self.P + self.R)

        # Update step: adjust the estimate with the measurement residual
        self.x = self.x + K * (measurement - self.x)
        # Update the uncertainty
        self.P = (1 - K) * self.P

        return self.x

    def get_state(self) -> float:
        """
        Get the current state estimate.

        Returns:
            float: The current estimated state value.
        """
        return self.x

    def get_variance(self) -> float:
        """
        Get the current estimate uncertainty (variance of the estimate).

        Returns:
            float: The current estimate variance.
        """
        return self.P

    def reset(self, value: Optional[float] = None, estimate_error: Optional[float] = None) -> None:
        """
        Reset the filter state to a new initial value and/or estimate error.

        Parameters:
            value (float, optional): New initial value for the state.
            If not provided, the current state is retained.
            estimate_error (float, optional): New initial estimate error (uncertainty).
            If not provided, the current uncertainty is retained.
        """
        if value is not None:
            self.x = value
        if estimate_error is not None:
            self.P = estimate_error
