# POPR
Reticulum LXM distribution based on Post Office Protocol

Personal note: We owe a large debt to the pioneers of the digital age, and I hope those responsible for these protocols, as well as all the protocols that have fallen out of use, know the debt we owe them and the joy I've found following their footsteps.

## Questions:

### Why POP?

Why not? Glib answers aside, the early Internet and Reticulum have similar needs and objectives. Simple, robust systems with high efficiency are preferred over lumbering do-all programs with huge resource footprints. The narrow feature set that still enables full operation is very useful and aligns with the values of Reticulum.

### Why are you using strings instead of control characters?

There's a tradeoff in efficiency for interoperability. It's inevitable someone will extend the commands in this list. It's likely more than one person will do so. By maintaining a four byte, human readable command list, the chance of collisions are reduced. There is a lower chance of a command like NEXT being misunderstood buy a different implementation than 0x1A being mapped to different commands in different implementations. An additional four bytes of overhead (including a delimiter) is an accepable loss compared to the headers and other overhead.

For responses, ASCII ACK and NACK may be acceptable replacements for OK+ and ERR-, but for the sake of parallelism with POP, it's a design decision with minimal negatives.

### Why can't I have multiple mailboxes?

While implementing multiple mailboxes is possible, it's deliberately difficult. Since all messages are stored unencrypted on the local system, multiple accounts managed by a single program or server is highly discouraged. Running multiple instances with differing paths and configurations is preferable to something that's too easy to expand into a very insecure system.

### Why doesn't this feature exist? 

Because POP3 is narrow in scope by design, and POPR adopts the same mentality. Everything needed to manage mail is present, and all the additional logic should be dealt with by the client, not the server. It is not meant for long term storage, it is not meant to perform advanced operations, and it's not meant to push notifications. It is meant to receive mail and transmit it to a client on request. 

POPR includes some SMTP-style operation for the sake of bi-directional communications, but POP3 is feature complete in RFC1939, and POPR implements their basic feature set, plus UIDL. This provides full functionality under Reticulum operation, and is sufficient for the purposes for which it was intended.
