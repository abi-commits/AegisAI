"""GraphSAGE model for fraud detection.

Lightweight inductive GNN that extracts node embeddings.
Intentionally simple - graph signals are context, not verdicts.

Uses PyTorch Geometric for implementation.
"""

from dataclasses import dataclass
from typing import Optional, Dict

import numpy as np

# PyTorch and PyG imports with graceful fallback
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric.data import Data
    from torch_geometric.nn import SAGEConv
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from aegis_ai.models.graph.schema import FraudGraph


@dataclass
class GraphSAGEConfig:
    """Configuration for GraphSAGE model."""
    input_dim: int = 8
    hidden_dim: int = 32
    output_dim: int = 16
    num_layers: int = 2
    dropout: float = 0.2
    aggregator: str = "mean"


if TORCH_AVAILABLE:
    class GraphSAGENetwork(nn.Module):
        """GraphSAGE neural network architecture.
        
        Multi-layer GraphSAGE with configurable aggregation.
        """
        
        def __init__(self, config: GraphSAGEConfig):
            super().__init__()
            self.config = config
            
            self.convs = nn.ModuleList()
            
            # First layer
            self.convs.append(SAGEConv(
                config.input_dim,
                config.hidden_dim,
                aggr=config.aggregator,
            ))
            
            # Hidden layers
            for _ in range(config.num_layers - 2):
                self.convs.append(SAGEConv(
                    config.hidden_dim,
                    config.hidden_dim,
                    aggr=config.aggregator,
                ))
            
            # Output layer
            if config.num_layers > 1:
                self.convs.append(SAGEConv(
                    config.hidden_dim,
                    config.output_dim,
                    aggr=config.aggregator,
                ))
            
            self.dropout = nn.Dropout(config.dropout)
        
        def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
            """Forward pass through GraphSAGE layers.
            
            Args:
                x: Node features [num_nodes, input_dim]
                edge_index: Edge indices [2, num_edges]
                
            Returns:
                Node embeddings [num_nodes, output_dim]
            """
            for conv in self.convs[:-1]:
                x = conv(x, edge_index)
                x = F.relu(x)
                x = self.dropout(x)
            
            # Final layer without activation
            x = self.convs[-1](x, edge_index)
            return x


class GraphSAGEModel:
    """GraphSAGE model for computing node embeddings.
    
    Generates embeddings on-the-fly from graphs.
    No training, persistence, or supervision - purely for inference.
    """
    
    def __init__(self, config: Optional[GraphSAGEConfig] = None):
        """Initialize GraphSAGE model.
        
        Args:
            config: Model configuration
        """
        if not TORCH_AVAILABLE:
            raise ImportError(
                "PyTorch and PyTorch Geometric required for GraphSAGE. "
                "Install with: pip install torch torch-geometric"
            )
        
        self.config = config or GraphSAGEConfig()
        self._model = GraphSAGENetwork(self.config)
        self._node_to_idx: Dict[str, int] = {}
    
    def _graph_to_pyg_data(self, graph: FraudGraph) -> "Data":
        """Convert FraudGraph to PyTorch Geometric Data.
        
        Args:
            graph: FraudGraph to convert
            
        Returns:
            PyG Data object
        """
        # Build node index mapping
        self._node_to_idx = {}
        for i, node_id in enumerate(graph.nodes.keys()):
            self._node_to_idx[node_id] = i
        
        # Build feature matrix
        num_nodes = len(graph.nodes)
        x = np.zeros((num_nodes, self.config.input_dim), dtype=np.float32)
        
        for node_id, node in graph.nodes.items():
            idx = self._node_to_idx[node_id]
            features = node.features[:self.config.input_dim]
            x[idx, :len(features)] = features
        
        # Build edge index (undirected)
        edge_list = []
        for edge in graph.edges:
            if edge.source_id in self._node_to_idx and edge.target_id in self._node_to_idx:
                src = self._node_to_idx[edge.source_id]
                dst = self._node_to_idx[edge.target_id]
                edge_list.append([src, dst])
                edge_list.append([dst, src])
        
        if edge_list:
            edge_index = torch.tensor(edge_list, dtype=torch.long).t().contiguous()
        else:
            edge_index = torch.zeros((2, 0), dtype=torch.long)
        
        x_tensor = torch.tensor(x, dtype=torch.float)
        return Data(x=x_tensor, edge_index=edge_index)
    
    def get_node_embedding(
        self,
        graph: FraudGraph,
        node_id: str
    ) -> np.ndarray:
        """Get embedding for a specific node.
        
        Args:
            graph: Graph containing the node
            node_id: Node to get embedding for
            
        Returns:
            Node embedding vector (zeros if node not found)
        """
        data = self._graph_to_pyg_data(graph)
        
        if node_id not in self._node_to_idx:
            return np.zeros(self.config.output_dim, dtype=np.float32)
        
        node_idx = self._node_to_idx[node_id]
        
        self._model.eval()
        with torch.no_grad():
            embeddings = self._model(data.x, data.edge_index)
            node_emb = embeddings[node_idx].numpy()
        
        return node_emb
