---
name: docker-management
description: Docker operations using direct tool calls for containers, images, networks, volumes, compose, and system management.
---

# Docker Tools Reference

## Container Tools
list_containers, run_container, start_container, stop_container, restart_container,
remove_container, get_container_logs, get_container_stats, exec_in_container, inspect_container

## Image Tools
list_images, pull_image, build_image, tag_image, remove_image, inspect_image, prune_images

## Network Tools
list_networks, create_network, remove_network, connect_container_to_network,
disconnect_container_from_network, inspect_network

## Volume Tools
list_volumes, create_volume, remove_volume, inspect_volume, prune_volumes

## Compose Tools
compose_up, compose_down, compose_ps, compose_logs

## System Tools
docker_system_info, docker_system_prune, docker_version

## Usage Rules
- Call tools directly - no routing or delegation needed.
- For bulk ops (e.g. stop all): list once, then act on each result.
- Ensure accessible means container is running with correct port mapping. Done.
- Never spawn helper containers (curl/wget) to verify connectivity.
