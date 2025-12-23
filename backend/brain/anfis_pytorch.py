import torch
import torch.nn as nn
import numpy as np

class GaussianMembership(nn.Module):
    """Layer 1: Learnable Gaussian Membership Functions"""
    def __init__(self, n_inputs, n_rules, input_ranges=None):
        super().__init__()
        self.n_inputs = n_inputs
        self.n_rules = n_rules
        
        # Learnable parameters: Mu (center) and Sigma (width)
        # Initializing nicely spread out centers
        if input_ranges is None:
            # Default standard initialization (0 +/- 1)
            self.mu = nn.Parameter(torch.randn(n_inputs, n_rules))
            self.sigma = nn.Parameter(torch.ones(n_inputs, n_rules))
        else:
            # Custom initialization covering the range
            # input_ranges is a list of tuples: [(min, max), (min, max)...]
            mus = []
            sigmas = []
            for i, (low, high) in enumerate(input_ranges):
                # Spread centers evenly across the range
                mu_i = torch.linspace(low, high, n_rules)
                mus.append(mu_i)
                
                # Width: cover about 1/n_rules of the range (with some overlap)
                sigma_i = torch.ones(n_rules) * ((high - low) / (n_rules - 1)) 
                sigmas.append(sigma_i)
            
            # Stack to shape (n_inputs, n_rules)
            self.mu = nn.Parameter(torch.stack(mus))
            self.sigma = nn.Parameter(torch.stack(sigmas))

    def forward(self, x):
        # x shape: (batch_size, n_inputs)
        # Expand x to (batch_size, n_inputs, n_rules) for broadcasting
        x = x.unsqueeze(2).expand(-1, -1, self.n_rules)
        
        # Gaussian formula: exp( -0.5 * ((x - mu) / sigma)^2 )
        exponent = -0.5 * ((x - self.mu) / self.sigma) ** 2
        return torch.exp(exponent)

class ANFIS(nn.Module):
    def __init__(self, n_inputs=2, n_rules=8, input_ranges=None):
        super().__init__()
        self.n_inputs = n_inputs
        self.n_rules = n_rules
        
        # Layer 1: Fuzzification
        self.fuzzification = GaussianMembership(n_inputs, n_rules, input_ranges=input_ranges)
        
        # Layer 4: Consequent (Linear functions: y = ax + b)
        # We need one linear function per rule
        # Since outputs are linear combinations of inputs: f_i = p_i * x + q_i
        # p_i are weights (n_rules, n_inputs), q_i are bias (n_rules)
        # Initialize to ZERO to prevent explosion with large inputs (pixel coords)
        self.consequent_weights = nn.Parameter(torch.zeros(n_rules, n_inputs))
        self.consequent_bias = nn.Parameter(torch.zeros(n_rules))

    def forward(self, x):
        # --- Layer 1: Membership Degrees ---
        # shape: (batch, n_inputs, n_rules)
        mu = self.fuzzification(x) 
        
        # --- Layer 2: Firing Strength (T-Norm / Product) ---
        # We multiply membership degrees across inputs for each rule
        # shape: (batch, n_rules)
        w = torch.prod(mu, dim=1) 
        
        # --- Layer 3: Normalization ---
        # shape: (batch, n_rules)
        w_sum = torch.sum(w, dim=1, keepdim=True)
        w_norm = w / (w_sum + 1e-8) # Avoid division by zero
        
        # --- Layer 4: Rule Outputs (Takagi-Sugeno) ---
        # Each rule outputs: f_i = p_i*x + q_i
        # x: (batch, n_inputs)
        # weights: (n_rules, n_inputs)
        # To compute p_i * x for each rule and batch:
        # We want result (batch, n_rules)
        
        # Expand x to (batch, 1, n_inputs)
        x_expanded = x.unsqueeze(1) # (batch, 1, n_inputs)
        
        # Weights (n_rules, n_inputs) -> Transpose to (n_inputs, n_rules) for matmul?
        # Or just element-wise multiply and sum?
        # Let's do:
        # (batch, 1, inputs) * (1, rules, inputs) -> (batch, rules, inputs) -> sum(-1) -> (batch, rules)
        
        # Broadcasting strategy:
        # x_expanded: (batch, 1, n_inputs)
        # weights_expanded: (1, n_rules, n_inputs)
        # product: (batch, n_rules, n_inputs)
        # sum: (batch, n_rules)
        
        term1 = torch.matmul(x, self.consequent_weights.t()) # (batch, n_inputs) @ (n_inputs, n_rules) -> (batch, n_rules)
        
        rule_outputs = term1 + self.consequent_bias # (batch, n_rules)
        
        # --- Layer 5: Aggregation ---
        # Final output = sum(w_norm * rule_output)
        # w_norm: (batch, n_rules)
        # rule_outputs: (batch, n_rules)
        output = torch.sum(w_norm * rule_outputs, dim=1, keepdim=True)
        
        return output
