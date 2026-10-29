# Remaining candidate blockers

Each failure below occurs in the unmodified native build or artifact resolver. None is attributed to the guard. Unsupported Boot/JVM/DSL/ambiguous-BOM boundaries are listed in results.csv, not counted as integration passes.

## #086 geoserver/geoserver-cloud

Pinned source: `ce6eeb08b761de819bbb0f6b42f79e2acc19d6b2`; selected build: `src/apps/infrastructure/gateway-webmvc/pom.xml`. [Commands/results](evidence/revisit/086.json), [logs](evidence/revisit/086.log).

- artifacts-online.log: [ERROR] Failed to execute goal on project gs-cloud-gateway-webmvc: Could not resolve dependencies for project org.geoserver.cloud.apps:gs-cloud-gateway-webmvc:jar:3.1.0-SNAPSHOT | [ERROR] dependency: org.geoserver.cloud:gs-cloud-spring-boot-starter:jar:3.1.0-SNAPSHOT (compile) | [ERROR] dependency: org.geoserver.cloud:gs-cloud-starter-observability:jar:3.1.0-SNAPSHOT (compile)
- bootstrap-reactor.log: [ERROR] Failed to execute goal on project gs-cloud-starter-observability: Could not resolve dependencies for project org.geoserver.cloud:gs-cloud-starter-observability:jar:3.1.0-SNAPSHOT | [ERROR] dependency: org.geoserver:gs-main:jar:3.1.0-CLOUD-SNAPSHOT (compile?) | [ERROR] 	Could not find artifact org.geoserver:gs-main:jar:3.1.0-CLOUD-SNAPSHOT in osgeo-snapshots (https://repo.osgeo.org/repository/snapshot/) | [ERROR] 	Could not find artifact org.geoserver:gs-main:jar:3.1.0-CLOUD-SNAPSHOT in central-portal-snapshots (https://central.sonatype.com/repository/maven-snapshots/)
- refresh-20261029-native-artifacts.log: [ERROR] Failed to execute goal on project gs-cloud-starter-observability: Could not resolve dependencies for project org.geoserver.cloud:gs-cloud-starter-observability:jar:3.1.0-SNAPSHOT | [ERROR] dependency: org.geoserver:gs-main:jar:3.1.0-CLOUD-SNAPSHOT (compile?) | [ERROR] 	Could not find artifact org.geoserver:gs-main:jar:3.1.0-CLOUD-SNAPSHOT in osgeo-snapshots (https://repo.osgeo.org/repository/snapshot/) | [ERROR] 	Could not find artifact org.geoserver:gs-main:jar:3.1.0-CLOUD-SNAPSHOT in central-portal-snapshots (https://central.sonatype.com/repository/maven-snapshots/)
