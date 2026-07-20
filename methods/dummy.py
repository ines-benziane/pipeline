from runner.method import Method, Result


class DummyMethod(Method):
    name = "dummy"
    version = "1.1"
    comparability_criteria = []

    def run(self, exam_dir, workdir):
        return Result(
            results={"ok": True},
            auto_valid=True,
            provenance = {"name": self.name, "version": self.version})
    
if __name__ == "__main__":
    dummy = DummyMethod()
    result = dummy.run("bidon", "bidule")
    print(result)