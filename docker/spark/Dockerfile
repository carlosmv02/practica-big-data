FROM eclipse-temurin:17-jdk-jammy AS builder
SHELL ["/bin/bash", "-lc"]

RUN apt-get update && apt-get install -y curl zip unzip ca-certificates && rm -rf /var/lib/apt/lists/*

RUN curl -s "https://get.sdkman.io" | bash

RUN source "$HOME/.sdkman/bin/sdkman-init.sh" && \
    sdk install scala 2.12.10 && \
    sdk install sbt 1.9.7

WORKDIR /build/flight_prediction
COPY flight_prediction/ ./

RUN source "$HOME/.sdkman/bin/sdkman-init.sh" && \
    sbt ++2.12.10 package


FROM apache/spark:3.5.3

USER root
WORKDIR /opt/app

COPY --from=builder /build/flight_prediction/target/scala-2.12/flight_prediction_2.12-0.1.jar /opt/app/flight_prediction.jar
COPY docker/spark/entrypoint.sh /opt/app/entrypoint.sh

RUN chmod +x /opt/app/entrypoint.sh && mkdir -p /opt/models
ENV MODEL_BASE_PATH=/opt/models

#USER 1001
ENTRYPOINT ["/opt/app/entrypoint.sh"]
