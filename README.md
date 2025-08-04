**frpc-for-windows**

适用于Windows的frpc客户端

**界面展示**

<img width="599" height="472" alt="image" src="https://github.com/user-attachments/assets/a03d70eb-d856-4cbb-9576-b93d11949eba" />

**界面功能介绍**


**1.重载配置,重载配置时需要配置
```
admin_addr = "127.0.0.1"
```

```
和admin_port = 7xxx
```
 用于动态加载实时读取。

```
[common]
server_addr = xxx.xxx.xxx.xxx
server_port = 7000
admin_addr = "127.0.0.1"
admin_port = 7900
token = xxxxxxx
[RDP]
type = tcp
local_ip = 127.0.0.1
local_port = xxxx
remote_port = 3389
```
**2.加载至注册表实现开机自启动**

