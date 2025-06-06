jdk_versions = ("1.8.0", "1.8", "8", "11", "17", "21", "1.7", "7", "22")
jdk_path = {
    "1.7": "",
    "7": "",
    "1.8.0": "",
    "1.8": "",
    "8": "",
    "11": "",
    "17": "",
    "21": "",
    "22": ""
}
mvn_dict = {
    "mvnw": "mvnw",
    "3.8.1": "",
    "3.6.3": "",
    "3.8.6": "",
    "3.9.9": ""
}
java_find_properties = [
    "java.version",
    "java-version",
    "java.source",
    "java.target",
    "version.java",
    "jdk.version",
    "jre.version",
    "javac.version",
    "javac.source",
    "javac.target",
    "maven.compiler.source",
    "maven.compiler.target",
    "maven.compiler.release",
    "maven-java.version",
    "java_source_version",
    "java_target_version",
    "java.source.version",
    "java.target.version",
    "target.java.version",
    "javaVersion",
    "target.jdk.version",
    "minimalJavaBuildVersion",
    "java.version.required",
    "java.compile.version",
    "target.jdk",
    "targetJdk",
    "minJdk",
    "min.jdk.version",
    "compile.version",
    "main.java.version",
    "project.build.sourceTarget",
    "project.java.version",
    "latest.java.version",
    "air.java.version",
    "debezium.java.source",
    "ugs.jvm.version",
    "orekit.compiler.source",
]
java_list = [
    "1.7",
    "1.8",
    "11",
    "17",
    "21",
    "22"
]
MVN_SKIPS = [
    "-Djacoco.skip",
    "-Dcheckstyle.skip",
    "-Dspotless.apply.skip",
    "-Drat.skip",
    "-Denforcer.skip",
    "-Danimal.sniffer.skip",
    "-Dmaven.javadoc.skip",
    "-Dmaven.gitcommitid.skip",
    "-Dfindbugs.skip",
    "-Dwarbucks.skip",
    "-Dmodernizer.skip",
    "-Dimpsort.skip",
    "-Dpmd.skip",
    "-Dxjc.skip",
    "-Dair.check.skip-all",
    "-Dlicense.skip",
    "-Denforcer.skip",
    "-Dremoteresources.skip",
    "-Dspotbugs.skip=true"
]