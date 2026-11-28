# What One Story has actually led with

Every published lead from 22/07/2026 to 28/11/2026, graded by hand on one
question: **is this an event?** The site promises the most important STORY of
the last 24 hours, so a backgrounder about a story, or a quote about one, is a
near miss rather than a hit.

Written 28/11/2026, after the site led with a Black Friday shopping cluster.
The point of grading all of them was to find out whether that was a one-off or
the visible end of something, and the answer is the table below: commerce was a
one-off, but **roughly a third of leads are not events**, and the largest
non-event class is not what prompted the audit.

Regenerate the inputs with `replay.py` plus the git history of `index.html`.
The grades are judgement and are meant to be argued with; the counts are not.

## The count

| Grade | Days | Share | Meaning |
|---|---|---|---|
| EVENT | 87 | 68% | something happened, was decided, or was announced with effect |
| STATEMENT | 20 | 16% | a figure said something and nothing else occurred |
| BACKGROUNDER | 12 | 9% | explainer, profile, preview or analysis, carrying no new event |
| SOFT | 6 | 5% | celebrity, lifestyle or trivia |
| ROUNDUP | 2 | 2% | a multi-story headline that should have been filtered |
| COMMERCE | 1 | 1% | shopping |

128 days. 87 were events; 41 were not.

## The finding that matters

**STATEMENT is the biggest non-event class, at 20 days.** Not commerce, which
happened once. A presidential quote is reprinted by every outlet in the sample
within hours, so it scores maximum coverage, maximum country and lean spread,
and perfect recency - the three things the score is made of. The scorer cannot
tell "the US imposed tariffs" from "the US president said he might", and the
second is cheaper to produce and more widely syndicated than the first.

Specimens, all of which led:

- Trump says there is a 'sick conspiracy' against AI, data centers
- Trump says triumphal arch will be military complex with drones and snipers
- Trump warns in UN speech he could 'annihilate' Iran without peace deal
- Increased US sanctions on Iran make large-scale war less likely: Bessent
- Microsoft rules out 'malicious activity' as cause for global outage

This is the same bias the archive-IDF experiment found from the other end.
Fitting TF-IDF across a 45-day window instead of one day discounts recurring
political vocabulary, and on the 18 days it changed the lead, nearly every
improvement was a disaster story surfacing past a political one. Two
independent measurements, one mechanical and one by hand, point at the same
structural tilt: **the score rewards being talked about over having happened.**

It was rejected as a clustering fix because it changed 18 days for a mixed
result and failed its own motivating case. Reconsider it as what it actually
is - a continuous anti-rhetoric term - and the 18 days want re-reading with
this table in hand.

## The rest

- **BACKGROUNDER, 12 days.** "Who is Lula?", "How did Christa Pike survive two
  lethal injections", "Why Nvidia CEO's affair matters", "Michigan race: all
  you need to know". These cluster with the event they explain and then win the
  hero slot, so the fix is in hero selection, not scoring.
- **ROUNDUP, 2 days.** Both predate the filters that would now catch them: the
  NPR Up First two-story signature (08/03) and a National digest headline
  (07/23). Evidence the filters work, not that they are missing something.
- **SOFT, 6 days.** Thin but defensible on a quiet day, which is what the new
  quiet-day note exists to say out loud.
- **COMMERCE, 1 day.** Filtered at fetch since 28/11/2026.

## Every lead

| Date | Grade | Outlets | Score | Lead |
|---|---|---|---|---|
| 2026-07-22 | STATEMENT |  |  | Mamdani backs off pledge to arrest Netanyahu citing lack of authority |
| 2026-07-23 | ROUNDUP | 21 | 0.214 | Trump trades new threats with Iran, alternative routes to Strait of Hormuz, and Saudi Arabia's nuclear deal |
| 2026-07-24 | EVENT | 11 | 0.135 | UNESCO adds Lebanese, West Bank sites to endangered list |
| 2026-07-25 | EVENT | 14 | 0.148 | India: Cockroaches end protest after education minister Dharmendra Pradhan resigns |
| 2026-07-26 | EVENT | 19 | 0.111 | German police hunt suspect in Berlin Pride attack: 1 dead and 16 injured |
| 2026-07-27 | EVENT | 11 | 0.206 | France: Macron holds crisis talks as wildfires spread |
| 2026-07-28 | EVENT | 14 | 0.132 | Japan: Strong earthquake hits Kumamoto, many feared dead |
| 2026-07-29 | EVENT | 13 | 0.253 | FIFA boss unveils $US20b plan to sell World Cup to Kushner consortium |
| 2026-07-30 | EVENT | 11 | 0.130 | Hundreds of migrants swim from Morocco to Spanish enclave of Ceuta |
| 2026-07-31 | STATEMENT | 16 | 0.201 | 'Never for sale': European nations vow World Cup boycott over FIFA plan |
| 2026-08-01 | EVENT | 8 | 0.196 | Trump administration drops Reflecting Pool vandalism charge and admits 'botched' repairs |
| 2026-08-02 | STATEMENT | 17 | 0.140 | No new Iran strikes for now amid deal hopes - Trump |
| 2026-08-03 | ROUNDUP | 8 | 0.154 | Todd Blanche rescinds 'anti-weaponization fund'. And, Trump calls off striking Iran |
| 2026-08-04 | BACKGROUNDER | 9 | 0.098 | Infantino could face UEFA lawsuit as he scrambles for FIFA presidency support |
| 2026-08-05 | BACKGROUNDER | 12 | 0.122 | El-Sayed's victory sends tremors through Democratic Party |
| 2026-08-06 | EVENT | 9 | 0.155 | Trump signs new orders restricting birthright citizenship |
| 2026-08-07 | EVENT | 12 | 0.137 | US appeals court blocks Trump’s US$400 million White House ballroom project |
| 2026-08-08 | EVENT | 13 | 0.173 | US Senate confirms Trump's ex lawyer as attorney general |
| 2026-08-09 | STATEMENT | 16 | 0.153 | Middle East: Netanyahu says Israel rejects Trump's Gaza plan |
| 2026-08-10 | EVENT | 15 | 0.146 | Colombia earthquake: Death toll rises to over 100 |
| 2026-08-11 | EVENT | 14 | 0.363 | Middle East: Trump took secret flight out of Turkey over Iran threat |
| 2026-08-12 | EVENT | 7 | 0.195 | NBA's Los Angeles Lakers to be sold to Josh Kushner, Bob Iger for record US$12.5 billion |
| 2026-08-13 | EVENT | 7 | 0.151 | Poland detains Russian over 'execution' plot in Warsaw: Tusk |
| 2026-08-14 | EVENT | 13 | 0.111 | UK: Nigel Farage beats a trash can in Clacton by-election |
| 2026-08-15 | EVENT | 10 | 0.213 | Lebanon reports 11 dead in strikes that Israel says targeted Hezbollah |
| 2026-08-16 | EVENT | 10 | 0.189 | Four 'extraordinary' Renaissance paintings stolen from Italian museum |
| 2026-08-17 | STATEMENT | 13 | 0.117 | Iran threatens to go on offensive in Strait of Hormuz if diplomacy with US fails |
| 2026-08-18 | EVENT | 8 | 0.188 | Meta trial over social media harm to children begins |
| 2026-08-19 | EVENT | 11 | 0.117 | Israeli military to open criminal probes into 2 Gaza attacks |
| 2026-08-20 | STATEMENT | 9 | 0.191 | Increased US sanctions on Iran make large-scale war less likely: Bessent |
| 2026-08-21 | EVENT | 9 | 0.194 | Supreme Court temporarily allows Trump ballroom construction to continue |
| 2026-08-22 | EVENT | 15 | 0.165 | US imposes 50% tariffs on some Canadian products as trade talks fail |
| 2026-08-23 | BACKGROUNDER | 10 | 0.229 | Ukraine: Could ex-defense minister challenge Zelenskyy? |
| 2026-08-24 | EVENT | 11 | 0.102 | US unveils 'economic D-Day' of sanctions to isolate Iran |
| 2026-08-25 | EVENT | 18 | 0.218 | US country music legend Dolly Parton dies aged 80 |
| 2026-08-26 | EVENT | 17 | 0.385 | Meta settles in US states lawsuit on teen user addiction |
| 2026-08-27 | EVENT | 14 | 0.308 | Trump signs order to rename Lake Ontario as Lake America |
| 2026-08-29 | EVENT | 13 | 0.171 | Russian strike on Kyiv-area warehouse sparks detonation, killing 37 |
| 2026-08-30 | EVENT | 9 | 0.178 | NASA launches first telescope named after female scientist |
| 2026-08-31 | EVENT | 15 | 0.157 | Messi retires from international football with 'nothing left to give' |
| 2026-09-01 | EVENT | 11 | 0.258 | Times Square stabbing in NYC leaves 1 dead, assailant killed |
| 2026-09-02 | SOFT | 9 | 0.147 | US sailors arrive in Thailand's Pattaya after record 250 days at sea |
| 2026-09-03 | EVENT | 15 | 0.114 | Gloria Steinem, feminist activist and journalist, dies at 92 |
| 2026-09-04 | EVENT | 8 | 0.289 | Volkswagen board approves plan to cut another 50,000 jobs |
| 2026-09-05 | EVENT | 13 | 0.136 | Russia to pause strikes against Kyiv amid Ukraine talks |
| 2026-09-06 | BACKGROUNDER | 11 | 0.128 | Saxony-Anhalt's state election will have a nationwide impact |
| 2026-09-07 | BACKGROUNDER | 16 | 0.180 | Saxony-Anhalt: Digesting the AfD's landmark election win |
| 2026-09-08 | EVENT | 15 | 0.238 | UK announces trade sanctions on Israeli settlements in occupied West Bank |
| 2026-09-09 | EVENT | 8 | 0.250 | Oil prices rise as Middle East conflict escalates |
| 2026-09-10 | EVENT | 7 | 0.104 | China: Cargo ship fire kills at least 25 |
| 2026-09-11 | EVENT | 12 | 0.136 | Americans mark 25 years since Sep 11 attacks amid enduring grief, reflection |
| 2026-09-12 | EVENT | 10 | 0.306 | Saudi Arabia shuts key oil pipeline after drone attack launched from Iraq |
| 2026-09-13 | EVENT | 13 | 0.093 | Indonesia rescuers search for 130 people after ferry sinks |
| 2026-09-14 | STATEMENT | 8 | 0.135 | Trump says there is a 'sick conspiracy' against AI, data centers |
| 2026-09-15 | SOFT | 11 | 0.139 | Ed Sheeran says it was 'not my decision' to drop Macklemore from tour |
| 2026-09-16 | EVENT | 8 | 0.107 | Gaza: At least 21 dead, including children, in building collapse |
| 2026-09-17 | EVENT | 13 | 0.147 | UN experts say grounds to believe US committed war crimes in Iran strikes |
| 2026-09-18 | EVENT | 12 | 0.221 | Warren Buffett steps down as Berkshire Hathaway chairman |
| 2026-09-19 | EVENT | 19 | 0.215 | Trump says he is banning CNN and Politico from White House |
| 2026-09-20 | STATEMENT | 12 | 0.264 | Trump says triumphal arch will be military complex with drones and snipers |
| 2026-09-21 | EVENT | 15 | 0.152 | US networks halt Trump coverage over White House ban |
| 2026-09-22 | STATEMENT | 7 | 0.318 | Trump warns in UN speech he could 'annihilate' Iran without peace deal |
| 2026-09-23 | STATEMENT | 11 | 0.132 | President tells Trump that Iran will never 'bend at the knee' |
| 2026-09-24 | EVENT | 16 | 0.184 | CNN, MS NOW, Politico regain access to White House |
| 2026-09-25 | SOFT | 9 | 0.291 | Xi wraps up US visit with trip to National Archives |
| 2026-09-26 | STATEMENT | 15 | 0.133 | Trump rejects Iranian proposal to open Hormuz and end fighting |
| 2026-09-27 | EVENT | 13 | 0.120 | UK: 5 arrested after 'major incident' near Fairford air base |
| 2026-09-28 | EVENT | 8 | 0.216 | SpaceX launches supersized Starship into orbit |
| 2026-09-29 | EVENT | 8 | 0.169 | Satirist launches site naming Cornell students accused in gang-rape lawsuit |
| 2026-09-30 | EVENT | 14 | 0.088 | Execution of US murderer Christa Pike halted shortly before it was due to happen |
| 2026-10-01 | EVENT | 11 | 0.267 | Tennessee halts woman's execution after 'failed' attempt |
| 2026-10-02 | STATEMENT | 12 | 0.194 | G7 countries say they will release '100 million barrels' of diesel and crude |
| 2026-10-03 | EVENT | 15 | 0.149 | Flydubai co-pilot attempted 'terrorist attack,' UAE says |
| 2026-10-04 | STATEMENT | 12 | 0.180 | Cornell president says university 'must do better' after frat house rape allegations |
| 2026-10-05 | EVENT | 16 | 0.124 | Right-wing Flávio Bolsonaro wins first round of Brazil election |
| 2026-10-06 | EVENT | 11 | 0.221 | Kenya reports first-ever Ebola death |
| 2026-10-07 | BACKGROUNDER | 9 | 0.184 | How did Christa Pike survive two lethal injections - and what happens now? |
| 2026-10-08 | BACKGROUNDER | 12 | 0.130 | Former Venezuelan President Nicolás Maduro expected to face more charges this week |
| 2026-10-09 | EVENT | 22 | 0.185 | Nobel Peace Prize 2026 goes to Navanethem 'Navi' Pillay for her efforts to promote peace and international law |
| 2026-10-10 | EVENT | 9 | 0.405 | Hurricane Isaias makes landfall in Florida |
| 2026-10-11 | EVENT | 15 | 0.120 | Trump announces 'energy ceasefire' between Russia and Ukraine |
| 2026-10-12 | EVENT | 13 | 0.227 | US federal agents search home of Trump critic Ilhan Omar |
| 2026-10-13 | EVENT | 12 | 0.211 | Houthis and Saudis strike each other in latest escalation |
| 2026-10-14 | SOFT | 16 | 0.198 | Pope walking and recovering 'as expected' after surgery, doctors say |
| 2026-10-15 | STATEMENT | 13 | 0.192 | Trump says military execution will not be livestreamed |
| 2026-10-16 | EVENT | 11 | 0.261 | Palestinians and US journalist injured by Israeli settlers in West Bank harvest attack |
| 2026-10-17 | EVENT | 14 | 0.186 | Trump puts new Russia sanctions on hold |
| 2026-10-18 | STATEMENT | 10 | 0.152 | Trump endorses Netanyahu in Israeli election |
| 2026-10-19 | EVENT | 10 | 0.193 | Australian MP seriously hurt in suspected car attack |
| 2026-10-20 | EVENT | 10 | 0.142 | Canada: Alberta rejects separation bid, CBC projects |
| 2026-10-21 | EVENT | 9 | 0.107 | New York congressional candidate Brad Lander says he was detained by IDF in the occupied West Bank |
| 2026-10-22 | STATEMENT | 9 | 0.133 | France's Macron says 'illegitimate' protests will be banned in coming days |
| 2026-10-23 | EVENT | 13 | 0.170 | Israel orders home demolitions after soldiers killed in West Bank |
| 2026-10-24 | EVENT | 12 | 0.218 | Jordan: Karak church shooting leaves 7 dead, dozens injured |
| 2026-10-25 | EVENT | 10 | 0.149 | Venezuelan opposition leader María Machado returns after months in exile |
| 2026-10-26 | BACKGROUNDER | 17 | 0.168 | Who is Lula? From ex-worker and prisoner to Brazil's president again |
| 2026-10-27 | EVENT | 10 | 0.258 | Flavio Bolsonaro's passports cancelled: Brazil police source |
| 2026-10-28 | EVENT | 20 | 0.178 | Dozens of people killed after high-speed trains collide in central Spain |
| 2026-10-29 | EVENT | 9 | 0.400 | European Central Bank (ECB) head Christine Lagarde to step down in February, before her term ends |
| 2026-10-30 | BACKGROUNDER | 10 | 0.220 | Tennessee woman Christa Pike describes pain after failed execution |
| 2026-10-31 | STATEMENT | 8 | 0.284 | U.K. PM open to slave trade apology but rules out financial reparations |
| 2026-11-01 | BACKGROUNDER | 7 | 0.086 | Michigan race: All you need to know about Abdul El-Sayed v Mike Rogers |
| 2026-11-02 | EVENT | 10 | 0.079 | European supermarkets targeted in second reported cyberattack |
| 2026-11-03 | STATEMENT | 9 | 0.106 | Trump says US will stop giving Israel aid after year-end |
| 2026-11-04 | EVENT | 11 | 0.136 | Democrat Abdul El-Sayed wins Michigan’s Senate race |
| 2026-11-05 | EVENT | 15 | 0.130 | British comedian and actor Russell Brand found guilty of rape |
| 2026-11-06 | EVENT | 17 | 0.280 | New bomb threats target Irish media, more European flights |
| 2026-11-07 | EVENT | 10 | 0.160 | At least 6 killed in shooting in Polish city of Krakow, police say |
| 2026-11-08 | EVENT | 12 | 0.185 | Israeli president tasks Gadi Eisenkot with forming government |
| 2026-11-09 | BACKGROUNDER | 19 | 0.135 | Why Nvidia CEO's affair with alleged Chinese spy matters |
| 2026-11-10 | STATEMENT | 15 | 0.270 | Defiant Hegseth blasts impeachment effort ahead of House vote |
| 2026-11-11 | EVENT | 13 | 0.266 | US Republicans derail push to impeach Defense Secretary Pete Hegseth |
| 2026-11-12 | BACKGROUNDER | 18 | 0.141 | Jensen Huang: Spy row, second affair leaves Nvidia without its rockstar CEO |
| 2026-11-13 | STATEMENT | 14 | 0.204 | Microsoft rules out 'malicious activity' as cause for global outage |
| 2026-11-14 | EVENT | 14 | 0.159 | US lifts nationwide ground stop for airports hours after halting all departures |
| 2026-11-15 | EVENT | 10 | 0.136 | SpaceX completes first-ever spaceship capture |
| 2026-11-16 | SOFT | 12 | 0.160 | British actor Robert Pattinson named as new James Bond |
| 2026-11-17 | EVENT | 14 | 0.226 | Nvidia forms national security committee after Huang affair |
| 2026-11-18 | EVENT | 13 | 0.184 | US House Democrats nominate Hakeem Jeffries for speaker |
| 2026-11-19 | EVENT | 14 | 0.227 | Myanmar committed genocide against Rohingya, top UN court rules |
| 2026-11-20 | EVENT | 8 | 0.279 | White House replaces cyber security chief after tech outages |
| 2026-11-21 | EVENT | 8 | 0.099 | Mexican drug lord on FBI's 10 most wanted list arrested in shoot-out |
| 2026-11-22 | EVENT | 14 | 0.138 | COP31: Climate deal 'not adopted,' summit president says |
| 2026-11-23 | EVENT | 20 | 0.141 | Nvidia reinstates Jensen Huang as CEO amid pressure from President Trump, investors |
| 2026-11-24 | EVENT | 10 | 0.262 | UK police arrest two men after break-in at William and Kate's home |
| 2026-11-25 | SOFT | 10 | 0.133 | US Army detonates unstable lead-based explosives in Iowa |
| 2026-11-26 | EVENT | 7 | 0.149 | Gérard Depardieu to stand trial for alleged rape of actress in 2018, court rules |
| 2026-11-27 | COMMERCE | 5 | 0.118 | All the best Walmart Black Friday deals to shop this weekend |
