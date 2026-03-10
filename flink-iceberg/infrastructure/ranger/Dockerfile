# Dockerfile for Apache Ranger Admin
# Build from source for ARM64 compatibility

FROM eclipse-temurin:17-jdk AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    wget \
    maven \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Download Apache Ranger source
WORKDIR /tmp
RUN wget https://downloads.apache.org/ranger/2.5.0/apache-ranger-2.5.0.tar.gz && \
    tar -xzf apache-ranger-2.5.0.tar.gz && \
    rm apache-ranger-2.5.0.tar.gz

# Build Ranger Admin
# This is a time-consuming step - skip tests to speed up
WORKDIR /tmp/apache-ranger-2.5.0
RUN mvn clean package -DskipTests -DskipITs -Drat.skip=true -Dcheckstyle.skip=true -Dpmd.skip=true

# Runtime stage
FROM eclipse-temurin:17-jre

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    wget \
    python3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Download MySQL connector
RUN wget -O /tmp/mysql-connector.jar https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/8.0.33/mysql-connector-j-8.0.33.jar

# Copy built Ranger Admin from builder
COPY --from=builder /tmp/apache-ranger-2.5.0/target/ranger-*-admin.tar.gz /tmp/

# Extract Ranger Admin
RUN mkdir -p /opt && \
    cd /opt && \
    tar -xzf /tmp/ranger-*-admin.tar.gz && \
    rm /tmp/ranger-*-admin.tar.gz && \
    mv ranger-* /opt/ranger-admin

# Install MySQL connector
RUN cp /tmp/mysql-connector.jar /opt/ranger-admin/ews/webapp/WEB-INF/lib/mysql-connector.jar && \
    rm /tmp/mysql-connector.jar

# Create directories
RUN mkdir -p /var/log/ranger /tmp/ranger-policy-cache

# Set environment variables
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk
ENV RANGER_ADMIN_HOME=/opt/ranger-admin
ENV RANGER_ADMIN_LOG_DIR=/var/log/ranger

# Expose port
EXPOSE 6080

# Set working directory
WORKDIR /opt/ranger-admin

# Copy entrypoint script
COPY docker-entrypoint.sh /opt/ranger-admin/entrypoint.sh
RUN chmod +x /opt/ranger-admin/entrypoint.sh

ENTRYPOINT ["/opt/ranger-admin/entrypoint.sh"]
CMD ["start"]
