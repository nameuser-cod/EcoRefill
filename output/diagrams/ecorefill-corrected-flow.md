# EcoRefill — Corrected activity flow

Both users and device owners sign in. The machine has no login. The four linked sections describe one workflow; purple callouts identify the destination and return point.

Points are credited only after a valid reward claim or a verified, successfully transferred purchase. A failed refill is recorded as failed, with its actual refund status. The machine returns to recycling mode after the refill result.

## 1. Sign in and choose an activity

User and owner sessions are independent. Machine operation does not require an owner to be logged in.

```mermaid
flowchart TD
    ustart(["USER<br/>Open EcoRefill app"])
    ulogin["USER<br/>Log in"]
    uvalid{"SYSTEM<br/>Credentials valid?"}
    uerror["SYSTEM<br/>Show login error"]
    udash["USER<br/>Open dashboard"]
    ostart(["OWNER<br/>Open EcoRefill app"])
    ologin["OWNER<br/>Log in"]
    ovalid{"SYSTEM<br/>Credentials valid?"}
    oerror["SYSTEM<br/>Show login error"]
    odash["OWNER<br/>Open dashboard"]
    uchoice{"USER<br/>Choose activity"}
    recycle["USER + MACHINE<br/>2. Recycling flow<br/>Return here when finished"]
    refill["USER + MACHINE<br/>3. Water refill flow<br/>Return here when finished"]
    ulogout(["USER<br/>Log out / End session"])
    ochoice{"OWNER<br/>Choose activity"}
    manage["OWNER<br/>Monitor / Handle alerts /<br/>Collect bottles and cans"]
    payments["OWNER + SYSTEM<br/>4. Join at owner review<br/>Return here after review"]
    ologout(["OWNER<br/>Log out / End session"])
    ustart --> ulogin
    ulogin --> uvalid
    uvalid -->|"No"| uerror
    uerror --> ulogin
    uvalid -->|"Yes"| udash
    ostart --> ologin
    ologin --> ovalid
    ovalid -->|"No"| oerror
    oerror --> ologin
    ovalid -->|"Yes"| odash
    udash --> uchoice
    uchoice -->|"Recycle"| recycle
    uchoice -->|"Refill"| refill
    uchoice -->|"Log out"| ulogout
    recycle --> udash
    refill --> udash
    odash --> ochoice
    ochoice -->|"Manage"| manage
    ochoice -->|"Payments"| payments
    ochoice -->|"Log out"| ologout
    manage --> odash
    payments --> odash
```

## 2. Recycle items and claim points

Entry: signed-in user chooses recycling. Accepted and rejected items both finish inspection before the next-item decision.

```mermaid
flowchart TD
    rstart(["USER + MACHINE<br/>Machine ready / Start recycling"])
    insert["USER<br/>Insert one item"]
    inspect["MACHINE<br/>Inspect the item"]
    accept{"MACHINE<br/>Item accepted?"}
    sort["MACHINE<br/>Sort item and add<br/>session points"]
    reject["MACHINE<br/>Return rejected item;<br/>add no points"]
    more{"USER<br/>More items?"}
    green["USER<br/>Press GREEN button"]
    earned{"MACHINE<br/>Session points > 0?"}
    none["MACHINE<br/>Show no reward"]
    reward["MACHINE<br/>Display reward QR"]
    scan["USER<br/>Scan reward QR in app"]
    claim{"SYSTEM<br/>Claim valid and unclaimed?"}
    claimerror["SYSTEM<br/>Show error; do not credit points"]
    retry{"USER<br/>Retry with valid QR?"}
    credit["SYSTEM<br/>Credit user points once;<br/>save reward transaction"]
    rend(["USER + MACHINE<br/>Show result; machine returns to<br/>recycling; user returns to Section 1"])
    rstart --> insert
    insert --> inspect
    inspect --> accept
    sort --> more
    reject --> more
    green --> earned
    reward --> scan
    scan --> claim
    credit --> rend
    accept -->|"Yes"| sort
    accept -->|"No"| reject
    more -->|"Yes"| insert
    more -->|"No"| green
    earned -->|"Yes"| reward
    earned -->|"No"| none
    none --> rend
    claim -->|"Yes"| credit
    claim -->|"No"| claimerror
    claimerror --> retry
    retry -->|"Yes"| scan
    retry -->|"No / Cancel"| rend
```

## 3. Select, pay for, and dispense water

Entry: signed-in user chooses refill. Payment approval adds points; only a validated refill request can start dispensing.

```mermaid
flowchart TD
    blue["USER<br/>Press BLUE button / Select refill"]
    qr["MACHINE<br/>Create refill session; display QR"]
    selection["USER<br/>Scan valid refill QR;<br/>select water amount"]
    confirm["USER<br/>Place container and<br/>confirm refill request"]
    validate["SYSTEM / MACHINE<br/>Validate session, amount,<br/>balance and machine availability"]
    reserve["SYSTEM<br/>Reserve refill and<br/>deduct points atomically"]
    dispense["MACHINE<br/>Dispense water; monitor container"]
    success["SYSTEM<br/>Save completed refill"]
    result["USER APP<br/>Show actual refill / refund result"]
    reset["MACHINE<br/>Return machine to recycling mode"]
    balance{"USER APP<br/>Enough points?"}
    buy{"USER<br/>Buy points?"}
    purchase["USER + OWNER<br/>4. Point purchase flow<br/>Return with purchase status"]
    resume["USER<br/>Resume refill; scan new QR<br/>if the session expired"]
    cancelbuy["USER<br/>Cancel refill"]
    valid{"SYSTEM / MACHINE<br/>Refill request valid?"}
    invalid["SYSTEM<br/>Show reason; no deduction<br/>and no dispensing"]
    retryrefill{"USER<br/>Retry refill?"}
    complete{"MACHINE<br/>Dispensing complete?"}
    stop["MACHINE<br/>Stop dispensing on<br/>error or timeout"]
    refund["SYSTEM<br/>Attempt refund of deducted points"]
    refunded{"SYSTEM<br/>Refund successful?"}
    refundok["SYSTEM<br/>Record failed refill<br/>and successful refund"]
    refundpending["SYSTEM<br/>Record failed refill;<br/>refund unresolved"]
    end(["USER<br/>Return to user dashboard<br/>Section 1"])
    blue --> qr
    qr --> selection
    selection --> balance
    confirm --> validate
    validate --> valid
    reserve --> dispense
    dispense --> complete
    success --> result
    result --> reset
    reset --> end
    purchase --> resume
    stop --> refund
    refund --> refunded
    balance -->|"Yes"| confirm
    balance -->|"No"| buy
    buy -->|"Yes"| purchase
    buy -->|"No"| cancelbuy
    resume -->|"Recheck QR and balance"| selection
    cancelbuy --> reset
    valid -->|"Yes"| reserve
    valid -->|"No"| invalid
    invalid --> retryrefill
    retryrefill -->|"Yes"| blue
    retryrefill -->|"No / Cancel"| reset
    complete -->|"Yes"| success
    complete -->|"No"| stop
    refunded -->|"Yes"| refundok
    refunded -->|"No"| refundpending
    refundok --> result
    refundpending --> result
```

## 4. Buy points and verify payment

Called from the refill selection page. The signed-in owner reviews purchases in Transactions; records do not replace owner login.

```mermaid
flowchart TD
    pstart(["USER<br/>Enter points to purchase"])
    available{"SYSTEM<br/>Purchase available?"}
    unavailable["USER APP<br/>Show unavailable;<br/>no payment / no points transferred"]
    submit["USER<br/>Pay via GCash and<br/>submit payment reference"]
    pending["SYSTEM<br/>Save pending purchase;<br/>no points credited yet"]
    review["SIGNED-IN OWNER<br/>Review received payment<br/>and purchase details"]
    status{"OWNER<br/>Review status?"}
    wait["SYSTEM<br/>Keep pending; wait for review<br/>No points credited"]
    rejectpay["OWNER / SYSTEM<br/>Reject payment; notify user<br/>No points credited"]
    transfer["SYSTEM<br/>Validate owner balance and<br/>transfer eligibility"]
    allowed{"SYSTEM<br/>Transfer allowed?"}
    blocked["SYSTEM<br/>Show transfer pending / error<br/>Do not credit points"]
    creditpoints["SYSTEM<br/>Transfer owner points to user<br/>and record approved purchase once"]
    pend(["USER APP<br/>Show purchase status; return to<br/>Section 3: resume refill and recheck<br/>QR validity and available balance"])
    pstart --> available
    submit --> pending
    pending --> review
    review --> status
    transfer --> allowed
    creditpoints --> pend
    available -->|"Yes"| submit
    available -->|"No"| unavailable
    unavailable --> pend
    status -->|"Pending"| wait
    wait --> review
    status -->|"Rejected"| rejectpay
    rejectpay --> pend
    status -->|"Approved"| transfer
    allowed -->|"Yes"| creditpoints
    allowed -->|"No"| blocked
    blocked --> pend
```
