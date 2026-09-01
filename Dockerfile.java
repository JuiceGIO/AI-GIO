# 升级4：Java 业务层容器（多阶段构建：Maven 打包 → JRE 运行，镜像只带 jar）

# 构建阶段
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /app
COPY --from=m2repo / /root/.m2/repository
COPY expense-approval/pom.xml .
COPY expense-approval/src ./src
RUN mvn -o -B -DskipTests package

# 运行阶段
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /app/target/expense-approval-*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
