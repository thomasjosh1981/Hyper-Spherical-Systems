#include "static_dictionary.hpp"

namespace tesseract {

const std::vector<std::string_view> STATIC_AI_WORDS = {
    "tensor", "gradient", "descent", "attention", "weights", "biases", "activation", "sigmoid", "softmax",
    "network", "neuron", "layer", "transformer", "encoder", "decoder", "embedding", "parameters", "backprop",
    "training", "testing", "validation", "inference", "quantization", "convolution", "pooling", "stride",
    "padding", "dropout", "regularization", "overfitting", "underfitting", "epoch", "batchsize", "optimizer",
    "adamw", "sgd", "rmsprop", "momentum", "heuristic", "stochastic", "hyperparameter", "checkpoint",
    "fine-tuning", "pretraining", "tokenization", "vocabulary", "sequence", "generation", "prediction",
    "classification", "regression", "clustering", "unsupervised", "supervised", "reinforcement", "policy",
    "reward", "agent", "environment", "states", "action", "q-learning", "deepmind", "openai", "pytorch",
    "tensorflow", "keras", "scikit-learn", "numpy", "pandas", "matplotlib", "seaborn", "cuda", "opencl",
    "vram", "nvme", "latency", "throughput", "bandwidth", "pipeline", "parallelism", "sharding", "distributed",
    "synchronous", "asynchronous", "thread", "process", "mutex", "deadlock", "cache", "prefetch", "eviction",
    "memory", "storage", "buffer", "stream", "binary", "matrix", "vector", "scalar", "tensorboard",
    "attention-map", "multi-head", "self-attention", "cross-attention", "query", "key", "value", "projection",
    "normalization", "layernorm", "batchnorm", "rmsnorm", "residual", "connection", "feedforward", "linear",
    "nonlinear", "differentiable", "derivative", "jacobian", "hessian", "loss", "criterion", "objective",
    "entropy", "cross-entropy", "kl-divergence", "cosine-similarity", "euclidean", "manhattan", "distance",
    "manifold", "dimensionality", "reduction", "pca", "t-sne", "umap", "autoencoder", "variational",
    "gan", "generator", "discriminator", "diffusion", "denoising", "noise", "latent", "space", "representation",
    "semantic", "syntax", "lexicon", "grammar", "preposition", "adverb", "adjective", "noun", "verb",
    "pronoun", "conjunction", "interjection", "article", "quantifier", "determiner", "phrase", "sentence",
    "paragraph", "document", "corpus", "dataset", "dataloader", "sampler", "collate", "augmentation",
    "transform", "resize", "normalize", "crop", "flip", "rotate", "translate", "affine", "perspective",
    "distortion", "blur", "contrast", "brightness", "saturation", "hue", "sharpness", "denoise", "super-resolution",
    "segmentation", "detection", "localization", "bounding-box", "iou", "ap", "map", "precision", "recall",
    "f1-score", "accuracy", "specificity", "sensitivity", "roc", "auc", "pr-curve", "confusion-matrix",
    "true-positive", "false-positive", "true-negative", "false-negative", "learning-rate", "weight-decay",
    "clip-grad", "warmup", "cosine-annealing", "step-lr", "plateau", "early-stopping", "save-best", "load-best",
    "inference-mode", "eval-mode", "train-mode", "zero-grad", "backward", "step", "zero-redundancy", "deepspeed",
    "megatron", "fairscale", "horovod", "mpi", "gloo", "nccl", "shm", "ipc", "socket", "http", "grpc",
    "rest", "api", "json", "yaml", "xml", "csv", "tsv", "parquet", "arrow", "feather", "hdf5", "netcdf",
    "sql", "nosql", "sqlite", "postgres", "mysql", "mongodb", "redis", "cassandra", "neo4j", "graphdb",
    "vector-db", "milvus", "faiss", "pinecone", "weaviate", "qdrant", "chromadb", "lancedb", "duckdb",
    "polars", "dask", "spark", "hadoop", "mapreduce", "hive", "pig", "flink", "storm", "beam", "kafka"
    // (This list represents a highly dense starting set of common AI terms; in production, 
    // it can be expanded dynamically or compiled from an offline text corpus analysis).
};

const std::vector<std::string_view> STATIC_AI_PAIRS = {
    "neural network", "vector space", "latent space", "loss function", "learning rate",
    "gradient descent", "weight decay", "batch size", "activation function", "transformer model",
    "language model", "deep learning", "machine learning", "reinforcement learning", "supervised learning",
    "unsupervised learning", "semi-supervised learning", "self-supervised learning", "transfer learning", "fine tuning",
    "pre training", "data augmentation", "cross validation", "confusion matrix", "precision recall",
    "f1 score", "roc curve", "cosine similarity", "euclidean distance", "manhattan distance",
    "multi head", "self attention", "cross attention", "query key", "value projection",
    "feed forward", "residual connection", "layer norm", "batch norm", "rms norm",
    "optim step", "zero grad", "early stopping", "hyperparameter tuning", "model checkpoint",
    "inference engine", "tensor cores", "cuda cores", "gpu memory", "vram allocation",
    "system ram", "nvme storage", "pcie bandwidth", "disk read", "disk write",
    "direct io", "asynchronous io", "predictive prefetch", "eviction policy", "cache hit",
    "cache miss", "staging pool", "loading zone", "model shard", "parity split",
    "decoy file", "obfuscation layer", "tripwire hook", "honey gate", "quantum safe",
    "post quantum", "kyber key", "dilithium signature", "blowfish crypt", "aes gcm",
    "hash map", "binary search", "sorting algorithm", "data frame", "sql query",
    "vector database", "semantic search", "embedding model", "context window", "attention span"
};

const std::vector<std::string_view> STATIC_AI_NGRAMS = {
    "large language model", "artificial neural network", "multi head self attention", "feed forward network",
    "recurrent neural network", "convolutional neural network", "deep belief network", "generative adversarial network",
    "variational autoencoder", "diffusion probabilistic model", "reinforcement learning agent", "markov decision process",
    "stochastic gradient descent", "root mean square propagation", "adaptive moment estimation", "rectified linear unit",
    "gaussian error linear unit", "swish activation function", "softmax activation function", "mean squared error",
    "binary cross entropy", "categorical cross entropy", "kullback leibler divergence", "principal component analysis",
    "t distributed stochastic neighbor embedding", "uniform manifold approximation and projection", "singular value decomposition", "floating point operations",
    "giga floating point operations", "tera floating point operations", "floating point operations per second", "mixed precision training",
    "automatic mixed precision", "distributed data parallel", "tensor parallel training", "pipeline parallel training",
    "fully sharded data parallel", "zero redundancy optimizer", "parameter efficient fine tuning", "low rank adaptation",
    "quantized low rank adaptation", "direct preference optimization", "reinforcement learning from human feedback", "reinforcement learning from ai feedback",
    "proximal policy optimization", "deep q network", "double deep q network", "dueling deep q network",
    "asynchronous advantage actor critic", "soft actor critic", "trust region policy optimization", "deterministic policy gradient"
};

} // namespace tesseract
