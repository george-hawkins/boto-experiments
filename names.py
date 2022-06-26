_RENDER_JOB_PREFIX = "render-job-"


class Names:
    def __init__(self, job_id):
        def name(s):
            return f"{_RENDER_JOB_PREFIX}{s}-{job_id}"

        self.log_group = name("log_group")
        self.bucket = name("bucket")
        self.dynamodb = name("dynamodb")
        self.worker = name("worker")
