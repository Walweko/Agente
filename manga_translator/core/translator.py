import os
import riva.client
import riva.client.proto.riva_nmt_pb2 as rnmt
import riva.client.proto.riva_nmt_pb2_grpc as rnmt_grpc

RIVA_SERVER  = "grpc.nvcf.nvidia.com:443"
FUNCTION_ID  = "0778f2eb-b64d-45e7-acae-7dd9b9b35b4d"

def _get_stub(api_key):
    auth = riva.client.Auth(
        uri=RIVA_SERVER,
        use_ssl=True,
        metadata_args=[
            ("function-id",   FUNCTION_ID),
            ("authorization", f"Bearer {api_key}"),
        ],
    )
    return rnmt_grpc.RivaTranslationStub(auth.channel)

def translate_batch(texts, api_key="", source_lang="en-US", target_lang="es-US"):
    api_key = api_key or os.getenv("NVIDIA_API_KEY", "")

    non_empty = [(i, t) for i, t in enumerate(texts) if t.strip()]
    if not non_empty:
        return [""] * len(texts)

    indices, to_translate = zip(*non_empty)
    stub    = _get_stub(api_key)
    request = rnmt.TranslateTextRequest(
        texts=list(to_translate),
        source_language=source_lang,
        target_language=target_lang,
    )
    response    = stub.TranslateText(request)
    translated  = [t.text.strip() for t in response.translations]
    result      = [""] * len(texts)
    for idx, trans in zip(indices, translated):
        result[idx] = trans
    return result
