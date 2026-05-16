from concurrent import futures
import os

import grpc

from backend.generated import inference_pb2_grpc
from .service import InferenceEngine


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=int(os.getenv("GRPC_WORKERS", "4"))))
    inference_pb2_grpc.add_InferenceEngineServicer_to_server(InferenceEngine(), server)
    server.add_insecure_port(f"0.0.0.0:{os.getenv('GRPC_PORT', '50051')}")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
