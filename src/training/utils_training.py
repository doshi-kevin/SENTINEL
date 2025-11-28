import torch
from torch.nn import CrossEntropyLoss
from torch.optim import Adam

def get_optimizer(model, lr=0.001):
    return Adam(model.parameters(), lr=lr)

def get_loss():
    return CrossEntropyLoss()

def accuracy(preds, labels):
    return (preds.argmax(dim=1) == labels).float().mean().item()
