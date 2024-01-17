# POPR
Reticulum LXM distribution based on Post Office Protocol

Personal note: We owe a large debt to the pioneers of the digital age, and I hope those responsible for these protocols, as well as all the protocols that have fallen out of use, know the debt we owe them and the joy I've found following their footsteps.

## Questions:

### Why POP?

Why not? Glib answers aside, the early Internet and Reticulum have similar needs and objectives. Simple, robust systems with high efficiency are preferred over lumbering do-all programs with huge resource footprints. The narrow feature set that still enables full operation is very useful and aligns with the values of Reticulum.

### Why can't I have multiple mailboxes?

While implementing multiple mailboxes is possible, it's deliberately difficult. Since all messages are stored unencrypted on the local system, multiple accounts managed by a single program or server is highly discouraged. Running multiple instances with differing paths and configurations is preferable to something that's too easy to expand into a very insecure system.

### Why doesn't this feature exist? 

Because POP3 is narrow in scope by design, and POPR adopts the same mentality. Everything needed to manage mail is present, and all the additional logic should be dealt with by the client, not the server. It is not meant for long term storage, it is not meant to perform advanced operations, and it's not meant to push notifications. It is meant to receive mail and transmit it to a client on request. 

