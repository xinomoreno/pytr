#!/usr/bin/env python3
import re

import coloredlogs
import json
import logging
import requests
from datetime import datetime
from locale import getdefaultlocale
from packaging import version
from pathlib import Path

log_level = None

RE_ISIN_LOGO = re.compile(r"^logos/([A-Z]{2}-?[\dA-Z]{9}-?\d)/v2$")

def get_logger(name=__name__, verbosity=None):
    '''
    Colored logging

    :param name: logger name (use __name__ variable)
    :param verbosity:
    :return: Logger
    '''
    global log_level
    if verbosity is not None:
        if log_level is None:
            log_level = verbosity
        else:
            raise RuntimeError('Verbosity has already been set.')

    shortname = name.replace('pytr.', '')
    logger = logging.getLogger(shortname)

    # no logging of libs
    logger.propagate = False

    if log_level == 'debug':
        fmt = '%(asctime)s %(name)-9s %(levelname)-8s %(message)s'
        datefmt = '%Y-%m-%d %H:%M:%S%z'
    else:
        fmt = '%(asctime)s %(message)s'
        datefmt = '%H:%M:%S'

    fs = {
        'asctime': {'color': 'green'},
        'hostname': {'color': 'magenta'},
        'levelname': {'color': 'red', 'bold': True},
        'name': {'color': 'magenta'},
        'programname': {'color': 'cyan'},
        'username': {'color': 'yellow'},
    }

    ls = {
        'critical': {'color': 'red', 'bold': True},
        'debug': {'color': 'green'},
        'error': {'color': 'red'},
        'info': {},
        'notice': {'color': 'magenta'},
        'spam': {'color': 'green', 'faint': True},
        'success': {'color': 'green', 'bold': True},
        'verbose': {'color': 'blue'},
        'warning': {'color': 'yellow'},
    }

    coloredlogs.install(level=log_level, logger=logger, fmt=fmt, datefmt=datefmt, level_styles=ls, field_styles=fs)

    return logger


def preview(response, num_lines=5):
    lines = json.dumps(response, indent=2).splitlines()
    head = '\n'.join(lines[:num_lines])
    tail = len(lines) - num_lines

    if tail <= 0:
        return f'{head}\n'
    else:
        return f'{head}\n{tail} more lines hidden'


def check_version(installed_version):
    log = get_logger(__name__)
    try:
        r = requests.get('https://api.github.com/repos/marzzzello/pytr/tags', timeout=1)
    except Exception as e:
        log.error('Could not check for a newer version')
        log.debug(str(e))
        return
    latest_version = r.json()[0]['name']

    if version.parse(installed_version) < version.parse(latest_version):
        log.warning(f'Installed pytr version ({installed_version}) is outdated. Latest version is {latest_version}')
    else:
        log.info('pytr is up to date')


def export_transactions(input_path, output_path, lang='auto'):
    '''
    Create a CSV with the deposits and removals ready for importing into Portfolio Performance
    The CSV headers for PP are language dependend

    i18n source from Portfolio Performance:
    https://github.com/buchen/portfolio/blob/93b73cf69a00b1b7feb136110a51504bede737aa/name.abuchen.portfolio/src/name/abuchen/portfolio/messages_de.properties
    https://github.com/buchen/portfolio/blob/effa5b7baf9a918e1b5fe83942ddc480e0fd48b9/name.abuchen.portfolio/src/name/abuchen/portfolio/model/labels_de.properties

    '''
    log = get_logger(__name__)
    if lang == 'auto':
        locale = getdefaultlocale()[0]
        if locale is None:
            lang = 'en'
        else:
            lang = locale.split('_')[0]

    if lang not in ['cs', 'de', 'en', 'es', 'fr', 'it', 'nl', 'pt', 'ru']:
        lang = 'en'

    i18n = {
        "date": {
            "cs": "Datum",
            "de": "Datum",
            "en": "Date",
            "es": "Fecha",
            "fr": "Date",
            "it": "Data",
            "nl": "Datum",
            "pt": "Data",
            "ru": "\u0414\u0430\u0442\u0430",
        },
        "type": {
            "cs": "Typ",
            "de": "Typ",
            "en": "Type",
            "es": "Tipo",
            "fr": "Type",
            "it": "Tipo",
            "nl": "Type",
            "pt": "Tipo",
            "ru": "\u0422\u0438\u043F",
        },
        "value": {
            "cs": "Hodnota",
            "de": "Wert",
            "en": "Value",
            "es": "Valor",
            "fr": "Valeur",
            "it": "Valore",
            "nl": "Waarde",
            "pt": "Valor",
            "ru": "\u0417\u043D\u0430\u0447\u0435\u043D\u0438\u0435",
        },
        "deposit": {
            "cs": 'Vklad',
            "de": 'Einlage',
            "en": 'Deposit',
            "es": 'Dep\u00F3sito',
            "fr": 'D\u00E9p\u00F4t',
            "it": 'Deposito',
            "nl": 'Storting',
            "pt": 'Dep\u00F3sito',
            "ru": '\u041F\u043E\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u0435',
        },
        "removal": {
            "cs": 'V\u00FDb\u011Br',
            "de": 'Entnahme',
            "en": 'Removal',
            "es": 'Removal',
            "fr": 'Retrait',
            "it": 'Prelievo',
            "nl": 'Opname',
            "pt": 'Levantamento',
            "ru": '\u0421\u043F\u0438\u0441\u0430\u043D\u0438\u0435',
        },
    }
    # Read relevant deposit timeline entries
    with open(input_path, encoding='utf-8') as f:
        timeline = json.load(f)

    # Write deposit_transactions.csv file
    # date, transaction, shares, amount, total, fee, isin, name
    log.info('Write deposit entries')
    with open(output_path, 'w', encoding='utf-8') as f:
        # f.write('Datum;Typ;Stück;amount;Wert;Gebühren;ISIN;name\n')
        csv_fmt = '{date};{type};{value}\n'
        header = csv_fmt.format(date=i18n['date'][lang], type=i18n['type'][lang], value=i18n['value'][lang])
        f.write(header)

        for event in timeline:
            event = event['data']
            dateTime = datetime.fromtimestamp(int(event['timestamp'] / 1000))
            date = dateTime.strftime('%Y-%m-%d')

            title = event['title']
            try:
                body = event['body']
            except KeyError:
                body = ''

            if 'storniert' in body:
                continue

            # Cash in
            if title in ['Einzahlung', 'Bonuszahlung']:
                f.write(csv_fmt.format(date=date, type=i18n['deposit'][lang], value=event['cashChangeAmount']))
            elif title == 'Auszahlung':
                f.write(csv_fmt.format(date=date, type=i18n['removal'][lang], value=abs(event['cashChangeAmount'])))
            # Dividend - Shares
            elif title == 'Reinvestierung':
                # TODO: Implement reinvestment
                log.warning('Detected reivestment, skipping... (not implemented yet)')

    log.info('Deposit creation finished!')


class Timeline:

    def __init__(self, tr):
        self.tr = tr
        self.log = get_logger(__name__)

        self.received_detail = 0
        self.requested_detail = 0
        self.num_timeline_details = 0

        self.events_without_docs = []
        self.events_with_docs = []

    async def get_next_timeline(self, response=None, max_age_timestamp=0):
        '''
        Get timelines and save time in list timelines.
        Extract timeline events and save them in list timeline_events

        '''

        if response is None:
            # empty response / first timeline
            self.log.info('Awaiting #1  timeline')
            # self.timelines = []
            self.num_timelines = 0
            self.timeline_events = []
            await self.tr.timeline()
        else:
            timestamp = response['data'][-1]['data']['timestamp']
            self.num_timelines += 1
            # print(json.dumps(response))
            self.num_timeline_details += len(response['data'])
            for event in response['data']:
                self.timeline_events.append(event)

            after = response['cursors'].get('after')
            if after is None:
                # last timeline is reached
                self.log.info(f'Received #{self.num_timelines:<2} (last) timeline')
                await self._get_timeline_details(5)
            elif max_age_timestamp != 0 and timestamp < max_age_timestamp:
                self.log.info(f'Received #{self.num_timelines + 1:<2} timeline')
                self.log.info('Reached last relevant timeline')
                await self._get_timeline_details(5, max_age_timestamp=max_age_timestamp)
            else:
                self.log.info(
                    f'Received #{self.num_timelines:<2} timeline, awaiting #{self.num_timelines + 1:<2} timeline'
                )
                await self.tr.timeline(after)

    async def _get_timeline_details(self, num_torequest, max_age_timestamp=0):
        '''
        request timeline details
        '''
        while num_torequest > 0:
            if len(self.timeline_events) == 0:
                self.log.info('All timeline details requested')
                return False

            else:
                event = self.timeline_events.pop()

            action = event['data'].get('action')
            # icon = event['data'].get('icon')
            msg = ''
            if max_age_timestamp != 0 and event['data']['timestamp'] > max_age_timestamp:
                msg += 'Skip: too old'
            # elif icon is None:
            #     pass
            # elif icon.endswith('/human.png'):
            #     msg += 'Skip: human'
            # elif icon.endswith('/CashIn.png'):
            #     msg += 'Skip: CashIn'
            # elif icon.endswith('/ExemptionOrderChanged.png'):
            #     msg += 'Skip: ExemptionOrderChanged'

            elif action is None:
                if event['data'].get('actionLabel') is None:
                    msg += 'Skip: no action'
            elif action.get('type') != 'timelineDetail':
                msg += f"Skip: action type unmatched ({action['type']})"
            elif action.get('payload') != event['data']['id']:
                msg += f"Skip: payload unmatched ({action['payload']})"

            if msg == '':
                self.events_with_docs.append(event)
            else:
                self.events_without_docs.append(event)
                self.log.debug(f"{msg} {event['data']['title']}: {event['data'].get('body')} {json.dumps(event)}")
                self.num_timeline_details -= 1
                continue

            num_torequest -= 1
            self.requested_detail += 1
            await self.tr.timeline_detail(event['data']['id'])

    async def timelineDetail(self, response, dl, max_age_timestamp=0):
        '''
        process timeline response and request timelines
        '''

        self.received_detail += 1
        # print(json.dumps(response))

        # when all requested timeline events are received request 5 new
        if self.received_detail == self.requested_detail:
            remaining = len(self.timeline_events)
            if remaining < 5:
                await self._get_timeline_details(remaining)
            else:
                await self._get_timeline_details(5)

        # print(f'len timeline_events: {len(self.timeline_events)}')
        isSavingsPlan = False
        if response.get('subtitleText') == 'Sparplan':
            isSavingsPlan = True
        else:
            # some savingsPlan don't have the subtitleText == 'Sparplan' but there are actions just for savingsPans
            # but maybe these are unneeded duplicates
            for section in response['sections']:
                if section['type'] == 'actionButtons':
                    for button in section['data']:
                        if button['action']['type'] in ['editSavingsPlan', 'deleteSavingsPlan']:
                            isSavingsPlan = True
                            break

        if response.get('subtitleText') != 'Sparplan' and isSavingsPlan is True:
            isSavingsPlan_fmt = ' -- SPARPLAN'
        else:
            isSavingsPlan_fmt = ''

        max_details_digits = len(str(self.num_timeline_details))
        self.log.info(
            f"{self.received_detail:>{max_details_digits}}/{self.num_timeline_details}: "
            + f"{response['titleText']} -- {response['subtitleText']}{isSavingsPlan_fmt}"
        )

        for section in response['sections']:
            if section['type'] == 'documents':
                for doc in section['documents']:
                    try:
                        timestamp = datetime.strptime(doc['detail'], '%d.%m.%Y').timestamp() * 1000
                    except ValueError:
                        timestamp = datetime.now().timestamp() * 1000
                    if max_age_timestamp == 0 or max_age_timestamp < timestamp:
                        # save all savingsplan documents in a subdirectory
                        if isSavingsPlan:
                            dl.dl_doc(doc, response['titleText'], response['subtitleText'], subfolder='Sparplan')
                        else:
                            # In case of a stock transfer (Wertpapierübertrag) add additional information to the document title
                            if response['titleText'] == 'Wertpapierübertrag':
                                body = next(item['data']['body'] for item in self.events_with_docs if
                                            item['data']['id'] == response['id'])
                                dl.dl_doc(doc, response['titleText'] + " - " + body, response['subtitleText'])
                            else:
                                dl.dl_doc(doc, response['titleText'], response['subtitleText'])

        if self.received_detail == self.num_timeline_details:
            self.log.info('Received all details')
            dl.output_path.mkdir(parents=True, exist_ok=True)
            with open(dl.output_path / 'other_events.json', 'w', encoding='utf-8') as f:
                json.dump(self.events_without_docs, f, ensure_ascii=False, indent=2)

            with open(dl.output_path / 'events_with_documents.json', 'w', encoding='utf-8') as f:
                json.dump(self.events_with_docs, f, ensure_ascii=False, indent=2)

            export_transactions(dl.output_path / 'other_events.json', dl.output_path / 'account_transactions.csv')

            dl.work_responses()


def get_amount(amountdict, decimalsep=','):
    """Extract amount as string"""
    digits = amountdict["fractionDigits"]
    currency = amountdict["currency"]
    amount = f'{amountdict["value"]:.{digits}f}'.replace('.', decimalsep)
    return amount, currency


def get_datetime(timestampstr):
    timestamp = datetime.fromisoformat(timestampstr)
    date = timestamp.strftime("%Y-%m-%d")
    time = timestamp.strftime("%H:%M")
    return timestamp, date, time


def get_key(parts, key, value):
    for part in parts:
        if isinstance(key, (list, tuple)):
            v = part
            for k in key:
                v = v[k]
        else:
            v = part[key]
        if v == value:
            return part


def get_isin(event):
    try:
        return get_key(event["details"]["sections"], ["action", "type"], "instrumentDetail")["action"]["payload"]
    except (TypeError, KeyError, IndexError):
        pass
    try:
        # No ISIN entry found, try to read it from icon
        m = RE_ISIN_LOGO.match(event["icon"])
        if m:
            return m.group(1)
    except (TypeError, KeyError):
        pass
    return ''

class Document:
    def __init__(self, data):
        self.title = data["title"]
        self.date = data["detail"]
        self.filedate = datetime.strptime(self.date, "%d.%m.%Y").strftime("%Y-%m-%d")
        self.url = data["action"]["payload"]
        self.id = data["id"]
        self.postboxType = data["postboxType"]


def get_documents(event, key=None):
    docs = [] if key is None else {}
    try:
        documents = get_key(event["details"]["sections"], "title", "Dokumente")
        for data in documents["data"]:
            try:
                doc = Document(data)
                if key is None:
                    docs.append(doc)
                else:
                    docs[data[key]] = doc
            except (TypeError, KeyError, IndexError):
                pass
    except (TypeError, KeyError, IndexError):
        pass
    return docs


class TimelineTransaction:

    def __init__(self, tr):
        self.tr = tr
        self.log = get_logger(__name__)

        self.timeline_transactions = []
        self.num_timeline_transactions = 0
        self.timeline_events_v2 = []
        self.received_detail_v2 = 0
        self.requested_detail_v2 = 0
        self.num_timeline_details_v2 = 0

        self.events_without_docs = []
        self.events_with_docs = []
        self.events = {}

        self.card_transactions = []
        self.payments = []
        self.direct_debit = []

    async def _get_timeline_details_v2(self, num_torequest, max_age_timestamp=0):
        '''
        request timeline details V2
        '''
        while num_torequest > 0:
            if len(self.timeline_events_v2) == 0:
                self.log.info('All timeline details V2 requested')
                return False

            event = self.timeline_events_v2.pop()
            self.events[event['id']] = event

            num_torequest -= 1
            self.requested_detail_v2 += 1
            await self.tr.timeline_detail_v2(event['id'])

    def event_coupon_payment(self, event, dl, max_age_timestamp=0):
        amount, currency = get_amount(event["amount"])
        timestamp, *_ = get_datetime(event["timestamp"])

        sections = event["details"]["sections"]
        overview_data = get_key(sections, "title", "Übersicht")["data"]
        description = get_key(overview_data, "title", "Ereignis")["detail"]["text"]
        asset = get_key(overview_data, "title", "Asset")["detail"]["text"]
        # no ISIN

        # Download invoice
        doc = get_documents(event)[0]
        filepath = Path(f'{doc.title} {description}') / f'{doc.filedate} - {description} - {asset}.pdf'
        dl.dl_doc_v2(doc.url, filepath, doc.id)
        return f'{description}: {asset}'

    def event_credit(self, event, dl, max_age_timestamp=0):
        amount, currency = get_amount(event["amount"])
        timestamp, *_ = get_datetime(event["timestamp"])

        sections = event["details"]["sections"]
        overview_data = get_key(sections, "title", "Übersicht")["data"]
        description = get_key(overview_data, "title", "Ereignis")["detail"]["text"]
        asset = get_key(overview_data, "title", "Asset")["detail"]["text"]
        isin = get_isin(event)

        # Download invoice
        doc = get_documents(event)[0]
        filepath = Path(f'{description}') / f'{doc.filedate} - {description} - {isin} {asset}.pdf'
        dl.dl_doc_v2(doc.url, filepath, doc.id)
        return f'{event["subtitle"]}: {event["title"]}'

    def event_interest_payout_created_(self, event, dl, max_age_timestamp=0):
        return f'Interest: {event["subtitle"]}'

    def event_order_executed_(self, event, dl, max_age_timestamp=0):
        return f'{event["subtitle"]}: {event["title"]}'

    def payment(self, event, counterstr):
        amount, currency = get_amount(event["amount"])
        timestamp, date, time = get_datetime(event["timestamp"])

        for section in event["details"]["sections"]:
            if section["title"] == "Übersicht":
                infos = {data["title"]: data["detail"]["text"] for data in section["data"]}
                counteraccount = infos[counterstr]
                status = infos["Status"]
                iban = infos["IBAN"]
                self.payments.append([date, time, counteraccount, iban, status, amount, currency])
                break
        return f'{amount} {currency}'

    def event_payment_inbound(self, event, dl, max_age_timestamp=0):
        s = self.payment(event, 'Von')
        return f'Payment inbound: {s}'

    def event_payment_outbound(self, event, dl, max_age_timestamp=0):
        s = self.payment(event, 'An')
        return f'Payment outbound: {s}'

    def event_payment_inbound_sepa_direct_debit(self, event, dl, max_age_timestamp=0):
        amount, currency = get_amount(event["amount"])
        timestamp, date, time = get_datetime(event["timestamp"])
        filedate = timestamp.strftime("%Y-%m-%d %H-%M")

        if not self.direct_debit:
            self.direct_debit.append(["Datum", "Uhrzeit", "Wert", "Währung", "Notiz"])
        self.direct_debit.append([date, time, amount, currency, "Lastschrifteinzug"])
        # Download invoice
        doc = get_documents(event)[0]
        filepath = Path(doc.title) / f'{doc.filedate} - Lastschrifteinzug.pdf'
        dl.dl_doc_v2(doc.url, filepath, doc.id)
        return f'Payment inbound: direct debit: {amount} {currency}'

    def event_repayment(self, event, dl, max_age_timestamp=0):
        amount, currency = get_amount(event["amount"])
        timestamp, *_ = get_datetime(event["timestamp"])

        sections = event["details"]["sections"]
        overview_data = get_key(sections, "title", "Übersicht")["data"]
        description = get_key(overview_data, "title", "Ereignis")["detail"]["text"]
        asset = get_key(overview_data, "title", "Asset")["detail"]["text"]
        isin = get_isin(event)

        # Download invoice
        doc = get_documents(event, "postboxType")["SHAREBOOKING"]
        filepath = Path(f'{doc.title} {description}') / f'{doc.filedate} - {description} - {isin} {asset}.pdf'
        dl.dl_doc_v2(doc.url, filepath, doc.id)
        return f'{description}: {isin} {asset}'

    def event_savings_plan_executed(self, event, dl, max_age_timestamp=0):
        doc = get_documents(event)[0]
        sections = event["details"]["sections"]
        isin = get_isin(event)
        asset = get_key(get_key(sections, "title", "Übersicht")["data"], "title", "Asset")["detail"]["text"]

        filepath = Path('Sparplan') / 'Abrechnung' / f'{doc.filedate} - Abrechnung Sparplan - {isin} {asset}.pdf'
        dl.dl_doc_v2(doc.url, filepath, doc.id)
        return f'Sparplan: {isin} {asset}'

    def event_benefits_saveback_execution(self, event, dl, max_age_timestamp=0):
        docs = get_documents(event, "postboxType")
        asset = event["title"]

        doc = docs.get("SAVINGS_PLAN_EXECUTED_V2")
        if doc:
            filepath = Path('Saveback') / 'Abrechung' / f'{doc.filedate} - Abrechnung Saveback - {asset}.pdf'
            dl.dl_doc_v2(doc.url, filepath, doc.id)

        doc = docs.get("COSTS_INFO_SAVINGS_PLAN_V2")
        if doc:
            filepath = Path('Saveback') / 'Kosteninformation' / f'{doc.filedate} - Kosteninformation Saveback - {asset}.pdf'
            dl.dl_doc_v2(doc.url, filepath, doc.id)

        doc = docs.get("BENEFIT_ACTIVATED")
        if doc:
            filepath = Path('Saveback') / 'Aktivierung' / f'{doc.filedate} - Aktivierung Saveback - {asset}.pdf'
            dl.dl_doc_v2(doc.url, filepath, doc.id)

        doc = docs.get("BENEFIT_DEACTIVATED")
        if doc:
            filepath = Path('Saveback') / 'Deaktivierung' / f'{doc.filedate} - Deaktivierung Saveback - {asset}.pdf'
            dl.dl_doc_v2(doc.url, filepath, doc.id)

        return f'Saveback: {asset}'

    def event_benefits_spare_change_execution(self, event, dl, max_age_timestamp=0):
        docs = get_documents(event, "postboxType")
        asset = event["title"]

        doc = docs.get("SAVINGS_PLAN_EXECUTED_V2")
        if doc:
            filepath = Path('Round-Up') / 'Abrechung' / f'{doc.filedate} - Abrechnung Round-Up - {asset}.pdf'
            dl.dl_doc_v2(doc.url, filepath, doc.id)

        doc = docs.get("COSTS_INFO_SAVINGS_PLAN_V2")
        if doc:
            filepath = Path('Round-Up') / 'Kosteninformation' / f'{doc.filedate} - Kosteninformation Round-Up - {asset}.pdf'
            dl.dl_doc_v2(doc.url, filepath, doc.id)

        doc = docs.get("BENEFIT_ACTIVATED")
        if doc:
            filepath = Path('Round-Up') / 'Aktivierung' / f'{doc.filedate} - Aktivierung Round-Up - {asset}.pdf'
            dl.dl_doc_v2(doc.url, filepath, doc.id)

        doc = docs.get("BENEFIT_DEACTIVATED")
        if doc:
            filepath = Path('Round-Up') / 'Deaktivierung' / f'{doc.filedate} - Deaktivierung Round-Up - {asset}.pdf'
            dl.dl_doc_v2(doc.url, filepath, doc.id)

        return f'Round-Up: {asset}'

    def event_card_successful_transaction(self, event, dl, max_age_timestamp=0):
        amount, currency = get_amount(event["amount"])
        timestamp, date, time = get_datetime(event["timestamp"])
        merchant = event["title"]
        saveback_amount = ""
        saveback_instrument = ""
        roundup_amount = ""
        roundup_instrument = ""
        for section in event["details"]["sections"]:
            data = section["data"]
            if isinstance(data, list):
                for entry in data:
                    detail = entry.get("detail", {})
                    if detail:
                        action = detail.get("action")
                        if action:
                            action_type = action.get("type", "")
                            if action_type == "benefitsSavebackOverview":
                                saveback_amount = detail["amount"].rstrip("  €")
                                saveback_instrument = detail["title"]
                            elif action_type == "benefitsRoundupOverview":
                                roundup_amount = detail["amount"].rstrip("  €")
                                roundup_instrument = detail["title"]

        if not self.card_transactions:
            self.card_transactions.append(
                ["Datum", "Uhrzeit", "Händler", "Wert", "Währung", "Saveback Betrag", "Saveback Sparplan",
                 "Round-Up Betrag", "Round-Up Sparplan"])
        self.card_transactions.append(
            [date, time, merchant, amount, currency, saveback_amount, saveback_instrument, roundup_amount,
             roundup_instrument])
        return f'Card transaction: {merchant}'

    def event_card_successful_verification(self, event, dl, max_age_timestamp=0):
        try:
            amount, currency = get_amount(event["amount"])
        except (TypeError, KeyError, IndexError):
            amount, currency = '0', 'EUR'
        timestamp, date, time = get_datetime(event["timestamp"])
        merchant = event["title"]
        self.card_transactions.append([date, time, merchant, amount, currency, '', '', '', ''])
        return f'Card verification: {merchant}'

    def event_unknown(self, event, dl, max_age_timestamp=0):
        try:
            name = event["title"]
            for doc in get_documents(event):
                filepath = Path('other') / Path(doc.title) / f'{doc.filedate} - {name}.pdf'
                dl.dl_doc_v2(doc.url, filepath, doc.id)
            return f'{event["eventType"]}: {doc.title}: {name}'
        except (KeyError, IndexError, TypeError):
            return f'{event["eventType"]} -- No document'

    async def timelineDetailV2(self, response, dl, max_age_timestamp=0):
        '''
        process timeline response and request timelines
        '''

        self.received_detail_v2 += 1
        # print(json.dumps(response))

        # when all requested timeline events are received request 5 new
        if self.received_detail_v2 == self.requested_detail_v2:
            remaining = len(self.timeline_events_v2)
            if remaining < 5:
                await self._get_timeline_details_v2(remaining)
            else:
                await self._get_timeline_details_v2(5)

        event = self.events[response["id"]]
        event["details"] = response

        event_handler = getattr(self, 'event_' + event["eventType"].lower(), self.event_unknown)
        name = event_handler(event, dl, max_age_timestamp)

        max_details_digits = len(str(self.num_timeline_details_v2))
        self.log.info(
            f"{self.received_detail_v2:>{max_details_digits}}/{self.num_timeline_details_v2}: "
            + f"{name}"
        )

        if self.received_detail_v2 == self.num_timeline_details_v2:
            self.log.info('Received all details V2')
            dl.output_path.mkdir(parents=True, exist_ok=True)
            # with open(dl.output_path / 'other_events.json', 'w', encoding='utf-8') as f:
            #    json.dump(self.events_without_docs, f, ensure_ascii=False, indent=2)

            with open(dl.output_path / 'all_events.json', 'w', encoding='utf-8') as f:
                json.dump(list(self.events.values()), f, ensure_ascii=False, indent=2)

            # with open(dl.output_path / 'events_with_documents.json', 'w', encoding='utf-8') as f:
            #   json.dump(self.events_with_docs, f, ensure_ascii=False, indent=2)

            with open(dl.output_path / 'account_transactions.csv', 'w', encoding='utf-8') as f:
                for elements in self.payments:
                    f.write(";".join(elements))
                    f.write("\n")

            with open(dl.output_path / 'direct_debit.csv', 'w', encoding='utf-8') as f:
                for elements in self.direct_debit:
                    f.write(";".join(elements))
                    f.write("\n")

            with open(dl.output_path / 'card_transactions.csv', 'w', encoding='utf-8') as f:
                for elements in self.card_transactions:
                    f.write(";".join(elements))
                    f.write("\n")

            dl.work_responses()

    async def get_next_timeline_transactions(self, response=None, max_age_timestamp=0):
        '''
        Get timelineTransactions and save time in list timelineTransactions.
        Extract timeline events V2 and save them in list timeline_events_v2

        '''

        if response is None:
            # empty response / first timelineTransactions
            self.log.info('Awaiting #1  timelineTransactions')
            self.timeline_transactions = []
            self.num_timeline_transactions = 0
            self.timeline_events_v2 = []
            await self.tr.timeline_transactions()
        else:
            # print(json.dumps(response))
            timestamp = response['items'][-1]['timestamp']
            self.num_timeline_transactions += 1
            self.num_timeline_details_v2 += len(response['items'])
            for event in response['items']:
                self.timeline_events_v2.append(event)

            after = response['cursors'].get('after')
            if after is None:
                # last timelineTransactions is reached
                self.log.info(f'Received #{self.num_timeline_transactions:<2} (last) timelineTransactions')
                await self._get_timeline_details_v2(5)
            elif max_age_timestamp != 0 and timestamp < max_age_timestamp:
                self.log.info(f'Received #{self.num_timeline_transactions + 1:<2} timelineTransactions')
                self.log.info('Reached last relevant timelineTransactions')
                await self._get_timeline_details_v2(5, max_age_timestamp=max_age_timestamp)
            else:
                self.log.info(
                    f'Received #{self.num_timeline_transactions:<2} timelineTransactions, '
                    f'awaiting #{self.num_timeline_transactions + 1:<2} timelineTransactions'
                )
                await self.tr.timeline_transactions(after)

