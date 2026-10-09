"""Bounded codec for the separate macro bank used by mapping format 3.2.

This module edits bytes offline. It does not send macro writes or change button
bindings. Hardware write integration awaits a real bank capture and verification.
"""
from dataclasses import dataclass
import struct

BANK_SIZE = 81 * 20
MAX_MACROS = 10
MAX_ACTIONS = 256


@dataclass(frozen=True)
class Action:
    delay_ms: int
    key: int
    event: int


@dataclass(frozen=True)
class Macro:
    key: int
    mode: int
    interval_ms: int
    name: str
    actions: tuple[Action, ...]


@dataclass(frozen=True)
class Record:
    macro: Macro
    raw: bytes


@dataclass(frozen=True)
class Bank:
    version: int
    records: tuple[Record, ...]
    raw: bytes


def decode_bank(blob):
    if len(blob) != BANK_SIZE:
        raise ValueError('Expected an 81 × 20-byte macro bank')
    version,count = struct.unpack_from('<HH',blob)
    if count > MAX_MACROS:
        raise ValueError('Unknown or uninitialized macro bank; no changes made')
    offsets = [24 + 4*struct.unpack_from('<H',blob,4+2*i)[0] for i in range(count)]
    if any(off<24 or off+32>BANK_SIZE for off in offsets) or offsets != sorted(set(offsets)):
        raise ValueError('Invalid macro offsets')
    records=[];keys=set();total=0
    for i,offset in enumerate(offsets):
        key,n,mode = struct.unpack_from('<BHB',blob,offset)
        end=offset+32+4*n
        limit=offsets[i+1] if i+1<count else BANK_SIZE
        if end>limit or n>MAX_ACTIONS or key in keys:
            raise ValueError('Overlapping, oversized or duplicate macro record')
        total+=n
        if total>MAX_ACTIONS:
            raise ValueError('Macro bank exceeds 256 total actions')
        keys.add(key)
        raw=bytes(blob[offset:end])
        name=raw[12:32].rstrip(b'\xff\x00').decode('utf-8',errors='replace')
        interval=struct.unpack_from('<H',raw,4)[0]
        elapsed=0;actions=[]
        for j in range(n):
            timestamp,button,event=struct.unpack_from('<HBB',raw,32+4*j)
            if timestamp<elapsed:
                raise ValueError('Macro timestamps move backwards')
            actions.append(Action(timestamp-elapsed,button,event));elapsed=timestamp
        records.append(Record(Macro(key,mode,interval,name,tuple(actions)),raw))
    return Bank(version,tuple(records),bytes(blob))


def _integer(value,low,high,name):
    if type(value) is not int or not low<=value<=high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')


def _encode_macro(macro, previous=None):
    _integer(macro.key,0,23,'Activation button')
    _integer(macro.mode,0,3,'Macro mode')
    _integer(macro.interval_ms,0,65535,'Repeat interval')
    if not isinstance(macro.name,str) or '\x00' in macro.name:
        raise ValueError('Macro name must be text without null characters')
    name=macro.name.encode('utf-8')
    if len(name)>20:
        raise ValueError('Macro name exceeds 20 UTF-8 bytes')
    if not 1<=len(macro.actions)<=MAX_ACTIONS:
        raise ValueError('A macro needs 1–256 actions')
    # Reserved bytes belong to this record and are retained when it is edited.
    header=bytearray(previous.raw[:32] if previous else b'\xff'*32)
    struct.pack_into('<BHBH',header,0,macro.key,len(macro.actions),macro.mode,macro.interval_ms)
    if previous is None or previous.macro.name!=macro.name:
        header[12:32]=name.ljust(20,b'\xff')
    elapsed=0;events=bytearray()
    for action in macro.actions:
        _integer(action.delay_ms,0,65535,'Action delay')
        elapsed+=action.delay_ms
        if elapsed>65535:
            raise ValueError('Macro duration exceeds 65,535 ms')
        # New events are restricted to the documented buttons/directional
        # stick actions. Hold=5 is recognized by the reader but not generated
        # until its payload semantics are established.
        if action.event in (0,1):
            _integer(action.key,0,23,'Action button')
        elif action.event in (2,3):
            _integer(action.key,160,168,'Stick direction')
        else:
            raise ValueError('Unsupported macro event')
        if type(action.event) is not int:
            raise ValueError('Macro event must be an integer')
        events.extend(struct.pack('<HBB',elapsed,action.key,action.event))
    return bytes(header+events)


def replace_macro(blob, macro):
    """Build an edited bank without sending it. Unedited records retain all bytes."""
    bank=decode_bank(blob)
    matches=[r for r in bank.records if r.macro.key==macro.key]
    previous=matches[0] if matches else None
    record=_encode_macro(macro,previous)
    if previous and previous.macro==macro:
        return bank.raw
    records=[record if r is previous else r.raw for r in bank.records]
    if previous is None:records.append(record)
    if len(records)>MAX_MACROS:
        raise ValueError('The controller supports at most 10 macros')
    if sum((len(raw)-32)//4 for raw in records)>MAX_ACTIONS:
        raise ValueError('Macro bank exceeds 256 total actions')
    result=bytearray(b'\xff'*BANK_SIZE)
    struct.pack_into('<HH',result,0,bank.version,len(records))
    offset=24
    for i,raw in enumerate(records):
        if offset+len(raw)>BANK_SIZE:
            raise ValueError('Macro bank is full')
        struct.pack_into('<H',result,4+2*i,(offset-24)//4)
        result[offset:offset+len(raw)]=raw
        offset+=len(raw)
    decode_bank(result)  # Check offsets and cumulative timestamp geometry.
    return bytes(result)
